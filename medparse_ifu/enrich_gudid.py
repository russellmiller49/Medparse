"""
Enrichment of IFU records using AccessGUDID and OpenFDA APIs.

Provides regulatory enrichment including:
- UDI/GUDID device information
- FDA classification details
- GMDN terms
- MR safety status from regulatory databases
"""

import requests
import time
import logging
from typing import Optional, Dict, Any, List
from medparse_ifu.schema import IFURecord

logger = logging.getLogger(__name__)

# API endpoints
ACCESS_GUDID = "https://accessgudid.nlm.nih.gov/api/v2/devices/lookup.json"
ACCESS_GUDID_HISTORY = "https://accessgudid.nlm.nih.gov/api/v2/devices/history"
OPENFDA_UDI = "https://api.fda.gov/device/udi.json"
OPENFDA_CLASS = "https://api.fda.gov/device/classification.json"
OPENFDA_RECALL = "https://api.fda.gov/device/recall.json"


def _safe_get(
    url: str,
    params: Dict[str, Any],
    tries: int = 3,
    backoff: float = 0.5
) -> Optional[Dict[str, Any]]:
    """
    Safely make an API request with retries and exponential backoff.
    
    Args:
        url: API endpoint URL
        params: Query parameters
        tries: Number of retry attempts
        backoff: Initial backoff time in seconds
        
    Returns:
        JSON response or None if failed
    """
    for i in range(tries):
        try:
            response = requests.get(url, params=params, timeout=20)
            
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 404:
                logger.debug(f"Not found: {url} with params {params}")
                return None
            elif response.status_code == 429:  # Rate limited
                wait_time = backoff * (2 ** i)
                logger.warning(f"Rate limited, waiting {wait_time}s...")
                time.sleep(wait_time)
            else:
                logger.warning(f"API error {response.status_code}: {response.text}")
                
        except requests.exceptions.RequestException as e:
            logger.warning(f"Request failed: {e}")
            
        if i < tries - 1:
            time.sleep(backoff * (2 ** i))
    
    return None


def enrich_from_gudid(record: IFURecord) -> IFURecord:
    """
    Enrich IFU record with AccessGUDID data.
    
    Args:
        record: IFU record to enrich
        
    Returns:
        Enriched IFU record
    """
    # Try to find a UDI-DI to look up
    di = None
    if record.regulatory.udi_di:
        di = record.regulatory.udi_di[0]
    
    if not di:
        logger.info("No UDI-DI found, skipping GUDID enrichment")
        return record
    
    logger.info(f"Looking up GUDID for DI: {di}")
    
    # Query AccessGUDID
    gudid_data = _safe_get(ACCESS_GUDID, {"di": di})
    
    if not gudid_data or 'gudid' not in gudid_data:
        logger.warning(f"No GUDID data found for DI: {di}")
        return record
    
    device = gudid_data['gudid'].get('device', {})
    
    # Update manufacturer if not already set
    if not record.ifu_metadata.manufacturer and device.get('companyName'):
        record.ifu_metadata.manufacturer = device['companyName']
        logger.info(f"Set manufacturer: {device['companyName']}")
    
    # Update trade name if not already set
    if not record.ifu_metadata.trade_name and device.get('brandName'):
        record.ifu_metadata.trade_name = device['brandName']
        logger.info(f"Set trade name: {device['brandName']}")
    
    # Add FDA product code
    if device.get('fdaProductCode'):
        if not record.regulatory.product_codes:
            record.regulatory.product_codes = []
        if device['fdaProductCode'] not in record.regulatory.product_codes:
            record.regulatory.product_codes.append(device['fdaProductCode'])
            logger.info(f"Added product code: {device['fdaProductCode']}")
    
    # Add Basic UDI-DI (EU)
    if device.get('basicUdiDi'):
        record.regulatory.basic_udi_di = device['basicUdiDi']
        logger.info(f"Set Basic UDI-DI: {device['basicUdiDi']}")
    
    # Extract GMDN terms
    gmdn_terms = device.get('gmdnTerms', [])
    if gmdn_terms:
        extracted_terms = []
        for term_obj in gmdn_terms:
            if isinstance(term_obj, dict) and term_obj.get('term'):
                extracted_terms.append(term_obj['term'])
        
        if extracted_terms:
            record.regulatory.gmdn_terms = list(set(extracted_terms))
            logger.info(f"Added GMDN terms: {extracted_terms}")
    
    # Check for MR safety status in GUDID
    mr_info = device.get('mrSafety')
    if mr_info:
        if isinstance(mr_info, dict):
            status = mr_info.get('status')
        else:
            status = str(mr_info)
        
        if status:
            record.regulatory.mr_safety_status = status
            logger.info(f"Set MR safety status from GUDID: {status}")
            
            # Update the MRI safety section if not already set
            if not record.mri_safety:
                from medparse_ifu.schema import MRISafety, Provenance
                record.mri_safety = MRISafety(
                    status=status,
                    prov=Provenance(
                        doc_id=record.regulatory.prov.doc_id if record.regulatory.prov else "gudid",
                        source_path="AccessGUDID API",
                        sha256="",
                        pages=[]
                    )
                )
    
    # Extract catalog and model numbers if available
    catalog_nums = device.get('catalogNumber', [])
    if catalog_nums and isinstance(catalog_nums, list):
        if not record.regulatory.catalog_numbers:
            record.regulatory.catalog_numbers = []
        for num in catalog_nums:
            if num and num not in record.regulatory.catalog_numbers:
                record.regulatory.catalog_numbers.append(num)
    
    # Check for device sizes/dimensions
    sizes = device.get('deviceSizes', [])
    if sizes and not record.dimensions:
        from medparse_ifu.schema import Dimensions, Provenance
        dims = {}
        for size in sizes:
            if isinstance(size, dict):
                if size.get('sizeType') and size.get('size'):
                    dims[size['sizeType']] = f"{size['size']} {size.get('unit', '')}"
        
        if dims:
            record.dimensions = Dimensions(
                other_dims=dims,
                prov=Provenance(
                    doc_id="gudid",
                    source_path="AccessGUDID API",
                    sha256="",
                    pages=[]
                )
            )
            logger.info(f"Added dimensions from GUDID: {dims}")
    
    return record


def enrich_from_openfda_classification(record: IFURecord) -> IFURecord:
    """
    Enrich IFU record with OpenFDA classification data.
    
    Args:
        record: IFU record to enrich
        
    Returns:
        Enriched IFU record
    """
    # Need a product code to look up classification
    if not record.regulatory.product_codes:
        logger.info("No product codes found, skipping classification enrichment")
        return record
    
    product_code = record.regulatory.product_codes[0]
    logger.info(f"Looking up classification for product code: {product_code}")
    
    # Query OpenFDA classification
    class_data = _safe_get(
        OPENFDA_CLASS,
        {"search": f"product_code:{product_code}", "limit": 1}
    )
    
    if not class_data or 'results' not in class_data:
        logger.warning(f"No classification data found for product code: {product_code}")
        return record
    
    result = class_data['results'][0]
    
    # Extract device class (I, II, III)
    device_class = result.get('device_class')
    if device_class:
        logger.info(f"Device class: {device_class}")
        # Could add this to metadata or regulatory section if needed
    
    # Extract regulation number
    regulation_number = result.get('regulation_number')
    if regulation_number:
        logger.info(f"Regulation number: {regulation_number}")
    
    # Extract panel (medical specialty)
    panel = result.get('medical_specialty_description')
    if panel:
        logger.info(f"Medical specialty: {panel}")
    
    # Extract device name/type
    device_name = result.get('device_name')
    if device_name and not record.ifu_metadata.device_family:
        record.ifu_metadata.device_family = device_name
        logger.info(f"Set device family: {device_name}")
    
    return record


def enrich_from_openfda_udi(record: IFURecord) -> IFURecord:
    """
    Enrich IFU record with OpenFDA UDI data.
    
    Args:
        record: IFU record to enrich
        
    Returns:
        Enriched IFU record
    """
    # Need a UDI-DI to look up
    if not record.regulatory.udi_di:
        logger.info("No UDI-DI found, skipping OpenFDA UDI enrichment")
        return record
    
    di = record.regulatory.udi_di[0]
    logger.info(f"Looking up OpenFDA UDI for DI: {di}")
    
    # Query OpenFDA UDI
    udi_data = _safe_get(
        OPENFDA_UDI,
        {"search": f"di:{di}", "limit": 1}
    )
    
    if not udi_data or 'results' not in udi_data:
        logger.warning(f"No OpenFDA UDI data found for DI: {di}")
        return record
    
    result = udi_data['results'][0]
    
    # Extract brand name
    brand_name = result.get('brand_name')
    if brand_name and not record.ifu_metadata.trade_name:
        record.ifu_metadata.trade_name = brand_name
        logger.info(f"Set trade name from OpenFDA: {brand_name}")
    
    # Extract company name
    company_name = result.get('company_name')
    if company_name and not record.ifu_metadata.manufacturer:
        record.ifu_metadata.manufacturer = company_name
        logger.info(f"Set manufacturer from OpenFDA: {company_name}")
    
    # Extract catalog number
    catalog_number = result.get('catalog_number')
    if catalog_number:
        if not record.regulatory.catalog_numbers:
            record.regulatory.catalog_numbers = []
        if catalog_number not in record.regulatory.catalog_numbers:
            record.regulatory.catalog_numbers.append(catalog_number)
            logger.info(f"Added catalog number from OpenFDA: {catalog_number}")
    
    # Extract MRI safety information
    mri_safety = result.get('mri_safety')
    if mri_safety and not record.regulatory.mr_safety_status:
        record.regulatory.mr_safety_status = mri_safety
        logger.info(f"Set MR safety status from OpenFDA: {mri_safety}")
    
    return record


def check_for_recalls(record: IFURecord) -> List[Dict[str, Any]]:
    """
    Check for any recalls associated with the device.
    
    Args:
        record: IFU record to check
        
    Returns:
        List of recall records if found
    """
    recalls = []
    
    # Try different identifiers
    search_terms = []
    
    if record.regulatory.udi_di:
        search_terms.append(f"di:{record.regulatory.udi_di[0]}")
    
    if record.regulatory.product_codes:
        search_terms.append(f"product_code:{record.regulatory.product_codes[0]}")
    
    if record.ifu_metadata.manufacturer and record.ifu_metadata.trade_name:
        search_terms.append(
            f'firm_fei_number:"{record.ifu_metadata.manufacturer}" AND product_description:"{record.ifu_metadata.trade_name}"'
        )
    
    for search in search_terms:
        logger.info(f"Checking for recalls with: {search}")
        
        recall_data = _safe_get(
            OPENFDA_RECALL,
            {"search": search, "limit": 10}
        )
        
        if recall_data and 'results' in recall_data:
            for result in recall_data['results']:
                recall_info = {
                    'recall_number': result.get('recall_number'),
                    'reason': result.get('reason_for_recall'),
                    'classification': result.get('classification'),
                    'date_initiated': result.get('recall_initiation_date'),
                    'product_description': result.get('product_description'),
                    'code_info': result.get('code_info'),
                }
                recalls.append(recall_info)
                logger.warning(f"Found recall: {recall_info['recall_number']} - {recall_info['classification']}")
    
    return recalls


def enrich_from_ids(record: IFURecord, sources: List[str] = None) -> IFURecord:
    """
    Main enrichment function that calls various API sources.
    
    Args:
        record: IFU record to enrich
        sources: List of sources to use (gudid, openfda, etc.)
                If None, uses all available sources
        
    Returns:
        Enriched IFU record
    """
    if sources is None:
        sources = ['gudid', 'openfda']
    
    logger.info(f"Starting enrichment from sources: {sources}")
    
    if 'gudid' in sources:
        record = enrich_from_gudid(record)
    
    if 'openfda' in sources:
        record = enrich_from_openfda_udi(record)
        record = enrich_from_openfda_classification(record)
    
    # Check for recalls (always do this for safety)
    recalls = check_for_recalls(record)
    if recalls:
        logger.warning(f"Found {len(recalls)} recall(s) for this device")
        # Could add recalls to the record or save separately
    
    logger.info("Enrichment complete")
    return record