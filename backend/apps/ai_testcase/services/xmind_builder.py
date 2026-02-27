# -*- coding: utf-8 -*-
"""
XMind 文件生成器
将结构化用例数据转换为 XMind 新版格式(.xmind)
"""
import json
import zipfile
import os
import uuid
import tempfile
import logging

logger = logging.getLogger(__name__)


class XMindBuilder:
    """XMind 文件生成器"""

    @staticmethod
    def _make_id():
        return uuid.uuid4().hex[:26]

    @classmethod
    def _make_topic(cls, title, children=None, labels=None, structure_class=None):
        """构建一个 topic 节点"""
        topic = {
            "id": cls._make_id(),
            "class": "topic",
            "title": title,
        }
        if labels:
            topic["labels"] = labels if isinstance(labels, list) else [labels]
        if structure_class:
            topic["structureClass"] = structure_class
        if children:
            topic["children"] = {"attached": children}
        return topic

    @classmethod
    def _make_case_chain(cls, case_title, priority, precondition, steps, expected):
        """构建链式用例：用例名 → 前置条件 → 测试步骤 → 预期结果"""
        expected_topic = cls._make_topic(expected, labels=["预期结果"])
        steps_topic = cls._make_topic(steps, children=[expected_topic], labels=["测试步骤"])
        precondition_topic = cls._make_topic(precondition, children=[steps_topic], labels=["前置条件"])
        case_topic = cls._make_topic(case_title, children=[precondition_topic], labels=["用例标题", priority])
        return case_topic

    @classmethod
    def build_from_data(cls, data: dict) -> list:
        """将结构化用例数据转换为 XMind sheets 结构"""
        root_title = data.get("title", "测试用例")
        modules = data.get("modules", [])

        module_topics = []
        for mod in modules:
            func_topics = []
            for func in mod.get("functions", []):
                case_topics = []
                for case in func.get("cases", []):
                    case_topic = cls._make_case_chain(
                        case_title=case.get("name", ""),
                        priority=case.get("priority", "P1"),
                        precondition=case.get("precondition", "无"),
                        steps=case.get("steps", ""),
                        expected=case.get("expected", "")
                    )
                    case_topics.append(case_topic)

                func_topic = cls._make_topic(
                    func.get("name", ""),
                    children=case_topics,
                    labels=["功能点"]
                )
                func_topics.append(func_topic)

            module_topic = cls._make_topic(
                mod.get("name", ""),
                children=func_topics,
                labels=["模块"]
            )
            module_topics.append(module_topic)

        root_topic = cls._make_topic(
            root_title,
            children=module_topics,
            structure_class="org.xmind.ui.logic.right"
        )

        sheets = [{
            "id": cls._make_id(),
            "class": "sheet",
            "title": root_title,
            "rootTopic": root_topic,
            "theme": {
                "id": cls._make_id(),
                "centralTopic": {
                    "type": "topic",
                    "properties": {
                        "fo:font-family": "NSimSun, \u65b0\u5b8b\u4f53",
                        "svg:fill": "#3F51B5",
                        "fo:color": "#FFFFFF",
                        "fo:font-size": "28pt",
                        "border-line-color": "#3F51B5",
                        "shape-class": "org.xmind.topicShape.roundedRect",
                        "line-class": "org.xmind.branchConnection.curve",
                        "line-color": "#9E9E9E",
                        "line-width": "1pt"
                    }
                },
                "mainTopic": {
                    "type": "topic",
                    "properties": {
                        "fo:font-family": "NSimSun, \u65b0\u5b8b\u4f53",
                        "fo:font-size": "18pt",
                        "fo:color": "#212121",
                        "svg:fill": "#FFFFFF",
                        "border-line-color": "#ADADAD",
                        "shape-class": "org.xmind.topicShape.roundedRect",
                        "line-class": "org.xmind.branchConnection.curve",
                        "line-color": "#9E9E9E",
                        "line-width": "1pt"
                    }
                },
                "subTopic": {
                    "type": "topic",
                    "properties": {
                        "fo:font-family": "NSimSun, \u65b0\u5b8b\u4f53",
                        "fo:font-size": "18pt",
                        "fo:color": "#212121",
                        "svg:fill": "#FFFFFF",
                        "border-line-color": "#E0E0E0",
                        "shape-class": "org.xmind.topicShape.underline",
                        "line-class": "org.xmind.branchConnection.curve",
                        "line-color": "#9E9E9E",
                        "line-width": "1pt"
                    }
                }
            }
        }]

        return sheets

    @classmethod
    def save_to_file(cls, sheets: list, filepath: str):
        """保存为 .xmind 文件"""
        content_json = json.dumps(sheets, ensure_ascii=False)
        metadata_json = json.dumps({
            "creator": {"name": "WorkMind", "version": "1.0.0"},
            "dataStructureVersion": "2"
        }, ensure_ascii=False)
        manifest_json = json.dumps({
            "file-entries": {
                "content.json": {},
                "metadata.json": {}
            }
        }, ensure_ascii=False)

        if os.path.exists(filepath):
            os.remove(filepath)

        with zipfile.ZipFile(filepath, "w", zipfile.ZIP_STORED) as zf:
            zf.writestr("content.json", content_json)
            zf.writestr("metadata.json", metadata_json)
            zf.writestr("manifest.json", manifest_json)

        logger.info(f"[XMind] 已生成: {filepath}")

    @classmethod
    def build_and_save(cls, data: dict, filepath: str):
        """一步到位：构建并保存"""
        sheets = cls.build_from_data(data)
        cls.save_to_file(sheets, filepath)
        return filepath

    @classmethod
    def build_to_bytes(cls, data: dict) -> bytes:
        """构建并返回文件字节（用于 HTTP 下载响应）"""
        sheets = cls.build_from_data(data)
        content_json = json.dumps(sheets, ensure_ascii=False)
        metadata_json = json.dumps({
            "creator": {"name": "WorkMind", "version": "1.0.0"},
            "dataStructureVersion": "2"
        }, ensure_ascii=False)
        manifest_json = json.dumps({
            "file-entries": {
                "content.json": {},
                "metadata.json": {}
            }
        }, ensure_ascii=False)

        # 写入临时文件再读取字节
        tmp = tempfile.NamedTemporaryFile(suffix=".xmind", delete=False)
        tmp_path = tmp.name
        tmp.close()

        try:
            with zipfile.ZipFile(tmp_path, "w", zipfile.ZIP_STORED) as zf:
                zf.writestr("content.json", content_json)
                zf.writestr("metadata.json", metadata_json)
                zf.writestr("manifest.json", manifest_json)

            with open(tmp_path, "rb") as f:
                return f.read()
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
