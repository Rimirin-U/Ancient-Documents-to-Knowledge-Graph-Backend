# app/core/examples.py

few_shot_examples = [
    {
        "input_text": "立杜绝卖契人张三，今因正用不足，情愿将自己祖遗坐落土名南乡一都二图，地名大树下，田三亩六分，东至李四田，西至沟，南至路，北至王五山，四至分明。凭中立契，出卖与赵六名为业。三面言定，时值价纹银五十两整。其银笔下交足，并无短少。其田自卖之后，任凭赵六管业，张三日后子孙不得言赎，亦不得言找。恐口无凭，立此杜绝卖契为照。嘉庆五年三月十二日。凭中人李四、王五。代书人陈七。",
        "cot": """
1.  **Identify Document Type**: The phrase "立杜绝卖契人" (Person executing the irrevocable sale deed) indicates this is an "irrevocable sale" (杜绝卖).
2.  **Extract Seller**: "张三" is explicitly named as the seller (卖契人).
3.  **Extract Buyer**: "出卖与赵六" (sold to Zhao Liu) identifies "赵六" as the buyer.
4.  **Extract Subject**: "田三亩六分" (Field 3 mu 6 fen) located at "南乡一都二图，地名大树下".
5.  **Extract Boundaries**: "东至李四田，西至沟，南至路，北至王五山".
6.  **Extract Price**: "时值价纹银五十两整" (Current value fine silver 50 taels exactly).
7.  **Extract Date**: "嘉庆五年三月十二日" (Jiaqing 5th year, 3rd month, 12th day).
8.  **Extract Witnesses/Middlemen**: "凭中人李四、王五" (Middlemen Li Si, Wang Wu). "代书人陈七" (Scribe Chen Qi).
9.  **Analyze Special Terms**: "杜绝卖" (Irrevocable sale), "子孙不得言赎" (Descendants cannot claim redemption), "不得言找" (Cannot claim additional payment). These confirm the nature of the transaction.
10. **Construct Output**: Map these entities to the JSON structure.
""",
        "output_json": {
            "extracted_entities": {
                "date": {"text": "嘉庆五年三月十二日", "normalized_value": "1800-04-06", "confidence": 0.99},
                "sellers": [{"text": "张三", "confidence": 0.99}],
                "buyers": [{"text": "赵六", "confidence": 0.99}],
                "subject": {"text": "田三亩六分", "confidence": 0.98},
                "boundaries": {"text": "东至李四田，西至沟，南至路，北至王五山", "confidence": 0.98},
                "price": {"text": "纹银五十两", "normalized_value": "50 taels silver", "confidence": 0.99},
                "witnesses": [
                    {"text": "李四", "confidence": 0.95},
                    {"text": "王五", "confidence": 0.95},
                    {"text": "陈七", "confidence": 0.95}
                ],
                "special_terms": [
                    {"text": "杜绝卖", "confidence": 0.99},
                    {"text": "子孙不得言赎", "confidence": 0.99},
                    {"text": "不得言找", "confidence": 0.99}
                ]
            },
            "relationships": [
                {"source": "张三", "target": "赵六", "type": "sells_to"},
                {"source": "李四", "target": "张三", "type": "witnessed_for"},
                {"source": "王五", "target": "张三", "type": "witnessed_for"}
            ],
            "confidence_scores": {"overall": 0.98},
            "raw_text": "...",
            "ocr_corrections": []
        }
    },
    {
        "input_text": "立典契人李四，今因乏用，愿将己置水田一坵，坐落西村，土名如意坝，计租谷八担。东至大路，西至河，南至张三界，北至己业。凭中引至王五边承典。三面议定典价洋银一百元正。其银即日亲收足讫。其田限至光绪十年八月内取赎。如有无力，听从加价找贴，不得刁难。恐口无凭，立此典契为照。光绪三年八月中浣之五日。中人赵六。代笔孙八。",
        "cot": """
1.  **Identify Document Type**: "立典契人" (Person executing the mortgage/pawn deed) indicates a "mortgage/pawn" (典契).
2.  **Extract Seller/Mortgagor**: "李四" is the mortgagor.
3.  **Extract Buyer/Mortgagee**: "王五边承典" (Wang Wu takes the mortgage).
4.  **Extract Subject**: "水田一坵...计租谷八担".
5.  **Extract Boundaries**: "东至大路，西至河，南至张三界，北至己业".
6.  **Extract Price**: "典价洋银一百元正" (Mortgage price foreign silver 100 yuan).
7.  **Extract Date**: "光绪三年八月中浣之五日".
8.  **Extract Witnesses**: "中人赵六", "代笔孙八".
9.  **Analyze Special Terms**: "限至光绪十年八月内取赎" (Redemption limited to August, Guangxu 10th year). This is a "conditional sale/mortgage" with a redemption clause.
10. **Construct Output**: Note the difference from the previous "irrevocable sale".
""",
        "output_json": {
            "extracted_entities": {
                "date": {"text": "光绪三年八月中浣之五日", "normalized_value": "1877-09-21", "confidence": 0.98},
                "sellers": [{"text": "李四", "confidence": 0.99}],
                "buyers": [{"text": "王五", "confidence": 0.99}],
                "subject": {"text": "水田一坵", "confidence": 0.97},
                "boundaries": {"text": "东至大路，西至河，南至张三界，北至己业", "confidence": 0.97},
                "price": {"text": "洋银一百元", "normalized_value": "100 foreign silver dollars", "confidence": 0.99},
                "witnesses": [
                    {"text": "赵六", "confidence": 0.95},
                    {"text": "孙八", "confidence": 0.95}
                ],
                "special_terms": [
                    {"text": "典契", "confidence": 0.99},
                    {"text": "限至光绪十年八月内取赎", "confidence": 0.99}
                ]
            },
            "relationships": [
                {"source": "李四", "target": "王五", "type": "mortgages_to"},
                 {"source": "赵六", "target": "李四", "type": "witnessed_for"}
            ],
            "confidence_scores": {"overall": 0.97},
            "raw_text": "...",
            "ocr_corrections": []
        }
    },
    {
        "input_text": "立退耕字人王五，承祖遗旱地一块，坐落北山，东至崖，西至沟，南至地，北至路。原系承种张三之业，今因无力耕种，情愿退还张三管业。言定退价钱三千文。其钱即日收足。自退之后，永无瓜葛。恐口无凭，立此退耕字为照。宣统元年腊月二十日。中人赵六。",
        "cot": """
1.  **Identify Document Type**: "立退耕字人" (Person executing the tenancy surrender) indicates a "surrender of tenancy" (退耕).
2.  **Extract Tenant (Seller equivalent)**: "王五".
3.  **Extract Landlord (Buyer equivalent)**: "退还张三管业" (Return to Zhang San to manage).
4.  **Extract Subject**: "旱地一块".
5.  **Extract Boundaries**: "东至崖，西至沟，南至地，北至路".
6.  **Extract Price**: "退价钱三千文".
7.  **Extract Date**: "宣统元年腊月二十日".
8.  **Extract Witness**: "中人赵六".
9.  **Analyze Special Terms**: "永无瓜葛" (Sever all ties/claims forever).
10. **Construct Output**: This is a specific type of transaction involving tenancy rights.
""",
        "output_json": {
            "extracted_entities": {
                "date": {"text": "宣统元年腊月二十日", "normalized_value": "1910-01-30", "confidence": 0.96},
                "sellers": [{"text": "王五", "confidence": 0.99}],
                "buyers": [{"text": "张三", "confidence": 0.99}],
                "subject": {"text": "旱地一块", "confidence": 0.98},
                "boundaries": {"text": "东至崖，西至沟，南至地，北至路", "confidence": 0.98},
                "price": {"text": "钱三千文", "normalized_value": "3000 cash", "confidence": 0.99},
                "witnesses": [
                    {"text": "赵六", "confidence": 0.95}
                ],
                "special_terms": [
                    {"text": "退耕字", "confidence": 0.99},
                    {"text": "永无瓜葛", "confidence": 0.99}
                ]
            },
            "relationships": [
                {"source": "王五", "target": "张三", "type": "surrenders_tenancy_to"},
                {"source": "赵六", "target": "王五", "type": "witnessed_for"}
            ],
            "confidence_scores": {"overall": 0.96},
            "raw_text": "...",
            "ocr_corrections": []
        }
    }
]
