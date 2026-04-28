# -*- coding: utf-8 -*-

from apps.ai_testcase.services.dedupe import dedupe_result_json


def test_dedupe_result_json_removes_cross_module_upgrade_navigation_duplicate():
    data = {
        "title": "用户信息管理_测试用例",
        "modules": [
            {
                "name": "用户信息下拉菜单",
                "functions": [
                    {
                        "name": "功能入口交互",
                        "cases": [
                            {
                                "name": "升级入口跳转定价页",
                                "priority": "P0",
                                "steps": "点击升级入口",
                                "expected": "跳转至定价页，URL正确，页面加载成功",
                                "dedupe_key": "R3+happy+upgrade_redirect",
                            }
                        ],
                    }
                ],
            },
            {
                "name": "升级入口跳转",
                "functions": [
                    {
                        "name": "升级入口点击与跳转",
                        "cases": [
                            {
                                "name": "免费用户点击升级入口成功跳转定价页",
                                "priority": "P0",
                                "steps": "点击下拉菜单中的升级入口",
                                "expected": "页面跳转至定价页，URL正确，页面加载成功",
                                "dedupe_key": "R5+R6_happy_success",
                            }
                        ],
                    }
                ],
            },
        ],
    }

    deduped, report = dedupe_result_json(data, mode="focused")

    assert report["after_count"] == 1
    assert report["removed_as_duplicates"] == 1
    assert report["semantic_removed"][0]["signature"] == "upgrade_entry|navigate|pricing_page|success"
    cases = [
        case
        for module in deduped["modules"]
        for function in module["functions"]
        for case in function["cases"]
    ]
    assert len(cases) == 1
    assert "跨模块语义去重合并" in cases[0]["expected"]
