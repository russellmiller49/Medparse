from medparse.layout.captions import attach_captions

def test_table_caption_and_footnote():
    pages = [{
        "page_number": 5,
        "lines": [
            "Table 1: Comparison of silicone stents and self-expanding metallic stents (SEMS)",
            "Stent type Silicone SEMS",
            "* fully covered metallic stents may have the same rate as silicone stents."
        ]
    }]
    assets = {"tables": [{"page": 5, "number": 1}], "figures": []}
    attach_captions(pages, assets)
    t1 = assets["tables"][0]
    assert "Comparison of silicone stents" in t1["caption"]
    assert "fully covered metallic stents" in t1.get("footnote","")