# -*- coding: utf-8 -*-
"""
功能测试用例导入器
支持 xmind, xls, xlsx, csv 格式导入用例
"""
import os
import json
import re
import logging
import io
import zipfile
from typing import List, Dict, Any
from django.core.files.uploadedfile import UploadedFile

logger = logging.getLogger(__name__)


class BaseCaseImporter:
    """基础用例导入器"""
    
    def parse(self, file: UploadedFile) -> List[Dict[str, Any]]:
        """
        解析上传文件并返回用例数据列表
        
        Args:
            file: 待解析的上传文件对象
            
        Returns:
            List[Dict]: 用例数据列表，每个字典包含以下字段：
                - requirement_name: 需求名称
                - feature_name: 功能模块
                - name: 用例名称
                - preconditions: 前置条件
                - test_steps: 操作步骤列表
                - expected_result: 预期结果
                - priority: 优先级
                - tags: 标签列表
        """
        raise NotImplementedError


class XMindImporter(BaseCaseImporter):
    """XMind 文件导入器"""
    
    def parse(self, file: UploadedFile) -> List[Dict[str, Any]]:
        """解析 XMind 文件"""
        try:
            file_bytes = b''.join(chunk for chunk in file.chunks())
            # 优先解析新版本XMind格式（基于JSON格式）
            cases = self._parse_xmind_json_only(file_bytes)
            return cases
        except Exception as e:
            logger.error(f"解析 XMind 文件失败: {e}", exc_info=True)
            raise Exception(f"解析 XMind 文件失败: {str(e)}")
    
    def _parse_xmind_topic(self, topic: Dict, parent_title: str = "") -> List[Dict[str, Any]]:
        """递归解析 XMind 主题"""
        cases = []
        
        if not topic:
            return cases
        
        title = topic.get('title', '')
        full_title = f"{parent_title} - {title}" if parent_title else title
        
        # 如果有子主题，递归处理子主题
        if 'topics' in topic and topic['topics']:
            for subtopic in topic['topics']:
                cases.extend(self._parse_xmind_topic(subtopic, full_title))
        else:
            # 叶子节点，创建用例
            # 从备注和标签中提取用例信息
            note = topic.get('note', '')
            labels = topic.get('labels', [])
            
            case = {
                'requirement_name': '',
                'feature_name': '',
                'name': full_title or '未命名用例',
                'preconditions': '',
                'test_steps': [{'step': '步骤1', 'expected_result': '预期结果1'}],
                'priority': 'P2',
                'tags': labels if isinstance(labels, list) else []
            }
            cases.append(case)
        
        return cases

    def _parse_xmind_json_only(self, file_bytes: bytes) -> List[Dict[str, Any]]:
        """解析新版本XMind格式（基于JSON格式，使用 content.json）"""
        cases: List[Dict[str, Any]] = []
        try:
            with zipfile.ZipFile(io.BytesIO(file_bytes)) as zf:
                if 'content.json' not in zf.namelist():
                    return cases
                content_json = zf.read('content.json')
                return self._parse_xmind_json(content_json)
        except Exception as e:
            logger.error(f"解析 XMind JSON 失败: {e}", exc_info=True)
        return cases

    def _parse_xmind_json(self, content_json: bytes) -> List[Dict[str, Any]]:
        """解析标准 XMind content.json"""
        cases: List[Dict[str, Any]] = []
        try:
            data = json.loads(content_json.decode('utf-8'))
        except Exception as e:
            logger.error(f"解析 XMind JSON 失败: {e}", exc_info=True)
            return cases

        def get_title(node: Dict[str, Any]) -> str:
            return str(node.get('title', '')).strip()

        def iter_child_topics(node: Dict[str, Any]) -> List[Dict[str, Any]]:
            children = node.get('children') or {}
            if isinstance(children, dict):
                attached = children.get('attached')
                if isinstance(attached, list):
                    return attached
                topics = children.get('topics')
                if isinstance(topics, list):
                    return topics
            if isinstance(children, list):
                return children
            return []

        sheets = []
        if isinstance(data, list):
            sheets = data
        elif isinstance(data, dict):
            if 'rootTopic' in data:
                sheets = [data]
            elif 'sheets' in data and isinstance(data['sheets'], list):
                sheets = data['sheets']

        for sheet in sheets:
            root_topic = sheet.get('rootTopic') if isinstance(sheet, dict) else None
            if not isinstance(root_topic, dict):
                continue

            requirement_name = get_title(root_topic) or '未命名需求'
            for module_topic in iter_child_topics(root_topic):
                feature_name = get_title(module_topic) or '未命名模块'
                for case_topic in iter_child_topics(module_topic):
                    case_name = get_title(case_topic) or '未命名用例'
                    case = {
                        'requirement_name': requirement_name,
                        'feature_name': feature_name,
                        'name': case_name,
                        'preconditions': '',
                        'test_steps': [],
                        'priority': 'P2',
                        'tags': []
                    }

                    labels = case_topic.get('labels')
                    if isinstance(labels, list) and labels:
                        case['priority'] = str(labels[0]).strip()

                    for detail_topic in iter_child_topics(case_topic):
                        title = get_title(detail_topic)
                        if title.startswith('前置条件：'):
                            case['preconditions'] = title.replace('前置条件：', '', 1).strip()
                            continue
                        if title == '操作步骤':
                            steps = []
                            for step_topic in iter_child_topics(detail_topic):
                                step_title = get_title(step_topic)
                                step_text = ''
                                expected_text = ''
                                if step_title.startswith('步骤'):
                                    step_text = step_title.split('：', 1)[-1].strip()
                                    for exp_topic in iter_child_topics(step_topic):
                                        exp_title = get_title(exp_topic)
                                        if exp_title.startswith('预期结果'):
                                            expected_text = exp_title.split('：', 1)[-1].strip()
                                elif step_title.startswith('预期结果'):
                                    expected_text = step_title.split('：', 1)[-1].strip()
                                if step_text or expected_text:
                                    steps.append({
                                        'step': step_text,
                                        'expected_result': expected_text
                                    })
                            if steps:
                                case['test_steps'] = steps

                    if not case['test_steps']:
                        case['test_steps'] = [{'step': '步骤1', 'expected_result': '预期结果1'}]

                    cases.append(case)

        logger.info("XMind导入完成: json_cases_count=%s", len(cases))
        return cases


class ExcelImporter(BaseCaseImporter):
    """Excel 文件导入器（支持 .xls 和 .xlsx）"""
    
    def parse(self, file: UploadedFile) -> List[Dict[str, Any]]:
        """解析 Excel 文件"""
        try:
            import pandas as pd
            
            # 读取 Excel 文件
            df = pd.read_excel(file, sheet_name=0)
            
            # 映射列名到标准字段名（支持中英文列名）
            column_mapping = {
                '需求名称': 'requirement_name',
                '功能模块': 'feature_name',
                '用例名称': 'name',
                '优先级': 'priority',
                '前置条件': 'preconditions',
                '操作步骤': 'test_steps',
                '预期结果': 'expected_result',
            }
            
            # 标准化列名
            df.columns = [column_mapping.get(col, col) for col in df.columns]
            
            def split_lines(value: Any, kind: str) -> List[str]:
                if value is None:
                    return []
                text = str(value).strip()
                if not text:
                    return []
                lines = [line.strip() for line in text.split('\n') if line.strip()]
                cleaned = []
                for line in lines:
                    if kind == 'step':
                        line = re.sub(r'^步骤\s*\d+[:：]\s*', '', line)
                    elif kind == 'expected':
                        line = re.sub(r'^预期结果\s*\d+[:：]\s*', '', line)
                    cleaned.append(line)
                return cleaned

            cases = []
            for _, row in df.iterrows():
                raw_steps = row.get('test_steps', '')
                raw_expected = row.get('expected_result', '')

                steps_list = split_lines(raw_steps, 'step')
                expected_list = split_lines(raw_expected, 'expected')
                if steps_list or expected_list:
                    max_len = max(len(steps_list), len(expected_list))
                    test_steps = []
                    for i in range(max_len):
                        test_steps.append({
                            'step': steps_list[i] if i < len(steps_list) else '',
                            'expected_result': expected_list[i] if i < len(expected_list) else ''
                        })
                else:
                    test_steps = self._parse_test_steps(raw_steps)
                
                # 解析优先级
                priority = self._parse_priority(row.get('priority', 'P2'))
                
                
                case = {
                    'requirement_name': str(row.get('requirement_name', '')).strip(),
                    'feature_name': str(row.get('feature_name', '')).strip(),
                    'name': str(row.get('name', '未命名用例')).strip(),
                    'preconditions': str(row.get('preconditions', '')).strip(),
                    'test_steps': test_steps,
                    'priority': priority,
                    'tags': []
                }
                if not case['feature_name']:
                    case['feature_name'] = str(row.get('module_name', '')).strip()
                
                if case['name'] and case['name'] != '未命名用例':
                    cases.append(case)
            
            return cases
        except ImportError:
            logger.error("pandas 或 openpyxl 未安装，请执行: pip install pandas openpyxl")
            raise Exception("Excel 导入功能需要安装 pandas 或 openpyxl 库")
        except Exception as e:
            logger.error(f"解析 Excel 文件失败: {e}", exc_info=True)
            raise Exception(f"解析 Excel 文件失败: {str(e)}")
    
    def _parse_test_steps(self, steps_str: str) -> List[Dict[str, str]]:
        """解析操作步骤字符串"""
        if not steps_str:
            return [{'step': '步骤1', 'expected_result': '预期结果1'}]
        
        # 支持多种格式：
        # 1. JSON 格式: [{"step": "步骤1", "expected_result": "结果1"}]
        # 2. 换行分隔格式: 步骤1\n预期结果1\n步骤2\n预期结果2
        # 3. 分隔符格式: 步骤1;结果1|步骤2;结果2
        
        try:
            # 尝试解析为JSON
            if isinstance(steps_str, str) and steps_str.strip().startswith('['):
                steps = json.loads(steps_str)
                # 兼容旧格式，将expected字段转换为expected_result
                return [{
                    'step': step.get('step', ''),
                    'expected_result': step.get('expected_result', step.get('expected', ''))
                } for step in steps]
        except:
            pass
        
        # 尝试解析为换行分隔格式
        lines = str(steps_str).strip().split('\n')
        steps = []
        for i in range(0, len(lines), 2):
            step = lines[i].strip() if i < len(lines) else ''
            expected = lines[i + 1].strip() if i + 1 < len(lines) else ''
            if step:
                steps.append({'step': step, 'expected_result': expected})
        
        if not steps:
            steps = [{'step': str(steps_str), 'expected_result': ''}]
        
        return steps
    
    def _parse_priority(self, priority_str: str) -> str:
        """解析优先级"""
        if not priority_str:
            return 'P2'
        
        priority_str = str(priority_str).upper().strip()
        if priority_str in ['P0', 'P1', 'P2', 'P3']:
            return priority_str
        
        # 尝试从字符串中提取优先级
        if 'P0' in priority_str or '最高' in priority_str or '紧急' in priority_str:
            return 'P0'
        elif 'P1' in priority_str or '高' in priority_str:
            return 'P1'
        elif 'P3' in priority_str or '低' in priority_str:
            return 'P3'
        else:
            return 'P2'
    
    def _parse_tags(self, tags_str: str) -> List[str]:
        """解析标签"""
        if not tags_str:
            return []
        
        # 支持多种分隔符：逗号、分号、空格、中文逗号、中文分号
        tags = []
        for separator in [',', ';', ' ', '，', '；']:
            if separator in str(tags_str):
                tags = [tag.strip() for tag in str(tags_str).split(separator) if tag.strip()]
                break
        
        if not tags:
            tags = [str(tags_str).strip()]
        
        return tags


class CSVImporter(BaseCaseImporter):
    """CSV 文件导入器"""
    
    def parse(self, file: UploadedFile) -> List[Dict[str, Any]]:
        """解析 CSV 文件"""
        try:
            import pandas as pd
            
            # 读取 CSV 文件
            df = pd.read_csv(file, encoding='utf-8')
            
            # 如果UTF-8读取失败，尝试GBK编码
            if df.empty:
                file.seek(0)
                try:
                    df = pd.read_csv(file, encoding='gbk')
                except:
                    file.seek(0)
                    df = pd.read_csv(file, encoding='gb18030')
            
            # 映射列名到标准字段名（支持中英文列名）
            column_mapping = {
                '需求名称': 'requirement_name',
                '功能模块': 'feature_name',
                '用例名称': 'name',
                '优先级': 'priority',
                '前置条件': 'preconditions',
                '操作步骤': 'test_steps',
                '预期结果': 'expected_result',
            }
            
            # 标准化列名
            df.columns = [column_mapping.get(col, col) for col in df.columns]
            
            # 复用 Excel 导入器的解析逻辑
            excel_importer = ExcelImporter()
            
            def split_lines(value: Any, kind: str) -> List[str]:
                if value is None:
                    return []
                text = str(value).strip()
                if not text:
                    return []
                lines = [line.strip() for line in text.split('\n') if line.strip()]
                cleaned = []
                for line in lines:
                    if kind == 'step':
                        line = re.sub(r'^步骤\s*\d+[:：]\s*', '', line)
                    elif kind == 'expected':
                        line = re.sub(r'^预期结果\s*\d+[:：]\s*', '', line)
                    cleaned.append(line)
                return cleaned

            cases = []
            for _, row in df.iterrows():
                raw_steps = row.get('test_steps', '')
                raw_expected = row.get('expected_result', '')

                steps_list = split_lines(raw_steps, 'step')
                expected_list = split_lines(raw_expected, 'expected')
                if steps_list or expected_list:
                    max_len = max(len(steps_list), len(expected_list))
                    test_steps = []
                    for i in range(max_len):
                        test_steps.append({
                            'step': steps_list[i] if i < len(steps_list) else '',
                            'expected_result': expected_list[i] if i < len(expected_list) else ''
                        })
                else:
                    test_steps = excel_importer._parse_test_steps(raw_steps)

                priority = excel_importer._parse_priority(row.get('priority', 'P2'))
                
                case = {
                    'requirement_name': str(row.get('requirement_name', '')).strip(),
                    'feature_name': str(row.get('feature_name', '')).strip(),
                    'name': str(row.get('name', '未命名用例')).strip(),
                    'preconditions': str(row.get('preconditions', '')).strip(),
                    'test_steps': test_steps,
                    'priority': priority,
                    'tags': []
                }
                if not case['feature_name']:
                    case['feature_name'] = str(row.get('module_name', '')).strip()
                
                if case['name'] and case['name'] != '未命名用例':
                    cases.append(case)
            
            return cases
        except ImportError:
            logger.error("pandas 未安装，请执行: pip install pandas")
            raise Exception("CSV 导入功能需要安装 pandas 库")
        except Exception as e:
            logger.error(f"解析 CSV 文件失败: {e}", exc_info=True)
            raise Exception(f"解析 CSV 文件失败: {str(e)}")


def get_importer(file_name: str) -> BaseCaseImporter:
    """
    根据文件扩展名返回对应的导入器实例
    
    Args:
        file_name: 文件名
        
    Returns:
        BaseCaseImporter: 导入器实例
    """
    file_ext = os.path.splitext(file_name)[1].lower()
    
    if file_ext == '.xmind':
        return XMindImporter()
    elif file_ext in ['.xls', '.xlsx']:
        return ExcelImporter()
    elif file_ext == '.csv':
        return CSVImporter()
    else:
        raise ValueError(f"不支持的文件格式: {file_ext}")
