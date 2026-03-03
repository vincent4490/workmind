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
            List[Dict]: 用例数据列表，每个字典包含（与 AI 结构一致）：
                - title: 需求名称_测试用例
                - module_name: 模块名称
                - function_name: 功能点名称
                - name: 用例名称
                - priority: P0/P1/P2/P3
                - precondition: 前置条件（文本）
                - steps: 测试步骤（文本）
                - expected: 预期结果（文本）
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
                'title': '',
                'module_name': '',
                'function_name': '',
                'name': full_title or '未命名用例',
                'precondition': '',
                'steps': '1. 步骤1',
                'expected': '',
                'priority': 'P2'
            }
            if isinstance(labels, list) and labels:
                case['priority'] = str(labels[0]).strip()
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
        """
        解析 XMind content.json，仅支持四层结构（与 AI 导出一致）：
        root(主题) → 模块 → 功能点 → 用例
        用例节点下：前置条件 → 测试步骤 → 预期结果（或 前置条件：/测试步骤/预期结果 子节点）
        """
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

        def has_label(node: Dict[str, Any], label_substr: str) -> bool:
            labels = node.get('labels') or []
            if not isinstance(labels, list):
                return False
            return any(label_substr in str(lb) for lb in labels)

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

            # 第一层：主题
            title = get_title(root_topic) or '未命名需求'
            # 第二层：模块
            for module_topic in iter_child_topics(root_topic):
                module_name = get_title(module_topic) or '未命名模块'
                # 第三层：功能点
                for func_topic in iter_child_topics(module_topic):
                    function_name = get_title(func_topic) or '未命名功能点'
                    # 第四层：用例
                    for case_topic in iter_child_topics(func_topic):
                        case_name = get_title(case_topic) or '未命名用例'
                        case = {
                            'title': title,
                            'module_name': module_name,
                            'function_name': function_name,
                            'name': case_name,
                            'precondition': '',
                            'steps': '',
                            'expected': '',
                            'priority': 'P2',
                        }
                        # 优先级：用例节点的 labels（如 ["用例标题", "P0"]）
                        labels = case_topic.get('labels')
                        if isinstance(labels, list):
                            for lb in labels:
                                s = str(lb).strip().upper()
                                if s in ('P0', 'P1', 'P2', 'P3'):
                                    case['priority'] = s
                                    break

                        # 1) AI 导出链式：用例 → 前置条件(labels) → 测试步骤(labels) → 预期结果(labels)，各节点 title 为正文
                        for detail_topic in iter_child_topics(case_topic):
                            if has_label(detail_topic, '前置条件'):
                                case['precondition'] = get_title(detail_topic)
                                for step_topic in iter_child_topics(detail_topic):
                                    if has_label(step_topic, '测试步骤'):
                                        case['steps'] = get_title(step_topic)
                                        for exp_topic in iter_child_topics(step_topic):
                                            if has_label(exp_topic, '预期结果'):
                                                case['expected'] = get_title(exp_topic)
                                                break
                                        break
                                break

                        # 2) 兜底：按标题关键字解析（手改 XMind 或「前置条件：」/「测试步骤」子节点格式）
                        step_lines = []
                        expected_lines = []
                        for detail_topic in iter_child_topics(case_topic):
                            detail_title = get_title(detail_topic)
                            if not case['precondition'] and detail_title.startswith('前置条件：'):
                                case['precondition'] = detail_title.replace('前置条件：', '', 1).strip()
                                continue
                            if detail_title in ('操作步骤', '测试步骤'):
                                sub_topics = iter_child_topics(detail_topic)
                                if len(sub_topics) == 1 and not case['steps']:
                                    only_child = sub_topics[0]
                                    only_title = get_title(only_child)
                                    if only_title.startswith('预期结果') or (only_title and '预期' in only_title):
                                        case['steps'] = case.get('steps') or detail_title
                                        if not case['expected']:
                                            case['expected'] = only_title.split('：', 1)[-1].strip() if '：' in only_title else only_title
                                    else:
                                        step_lines.append(only_title)
                                        for exp_topic in iter_child_topics(only_child):
                                            exp_title = get_title(exp_topic)
                                            if exp_title.startswith('预期结果'):
                                                expected_lines.append(exp_title.split('：', 1)[-1].strip())
                                elif sub_topics and not case['steps']:
                                    for step_topic in sub_topics:
                                        step_title = get_title(step_topic)
                                        if step_title.startswith('步骤'):
                                            step_lines.append(step_title.split('：', 1)[-1].strip())
                                        elif step_title.startswith('预期结果') or '预期' in step_title:
                                            expected_lines.append(
                                                step_title.split('：', 1)[-1].strip() if '：' in step_title else step_title
                                            )
                                        else:
                                            step_lines.append(step_title)
                                        for exp_topic in iter_child_topics(step_topic):
                                            exp_title = get_title(exp_topic)
                                            if exp_title.startswith('预期结果'):
                                                expected_lines.append(exp_title.split('：', 1)[-1].strip())
                                elif not case['steps']:
                                    case['steps'] = detail_title or '1. 步骤1'
                                continue
                            if not case['expected'] and (detail_title.startswith('预期结果') or (detail_title and '预期' in detail_title)):
                                case['expected'] = detail_title.split('：', 1)[-1].strip() if '：' in detail_title else detail_title

                        if step_lines or expected_lines:
                            if step_lines:
                                case['steps'] = case.get('steps') or '\n'.join(f'{i+1}. {s}' for i, s in enumerate(step_lines))
                            if expected_lines:
                                case['expected'] = case.get('expected') or '\n'.join(expected_lines)
                        if not case.get('steps') and not case.get('expected'):
                            case['steps'] = '1. 步骤1'

                        cases.append(case)

        logger.info("XMind导入完成(四层结构): json_cases_count=%s", len(cases))
        return cases


class ExcelImporter(BaseCaseImporter):
    """Excel 文件导入器（支持 .xls 和 .xlsx）"""
    
    def parse(self, file: UploadedFile) -> List[Dict[str, Any]]:
        """解析 Excel 文件"""
        try:
            import pandas as pd
            
            # 读取 Excel 文件
            df = pd.read_excel(file, sheet_name=0)
            
            column_mapping = {
                '需求名称': 'title',
                '模块名称': 'module_name',
                '功能点名称': 'function_name',
                '功能模块': 'module_name',
                '用例名称': 'name',
                '优先级': 'priority',
                '前置条件': 'precondition',
                '测试步骤': 'steps',
                '操作步骤': 'steps',
                '预期结果': 'expected',
            }
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
                raw_steps = row.get('steps', '')
                raw_expected = row.get('expected', '')
                steps_list = split_lines(raw_steps, 'step')
                expected_list = split_lines(raw_expected, 'expected')
                if steps_list or expected_list:
                    steps_text = '\n'.join(f'{i+1}. {s}' for i, s in enumerate(steps_list)) if steps_list else ''
                    expected_text = '\n'.join(expected_list) if expected_list else ''
                else:
                    test_steps = self._parse_test_steps(raw_steps)
                    steps_text = '\n'.join(f'{i+1}. {(s.get("step") or "").strip()}' for i, s in enumerate(test_steps))
                    expected_text = '\n'.join((s.get('expected_result') or '').strip() for s in test_steps)

                priority = self._parse_priority(row.get('priority', 'P2'))
                title = str(row.get('title', '')).strip()
                module_name = str(row.get('module_name', '')).strip()
                function_name = str(row.get('function_name', '')).strip()
                name = str(row.get('name', '未命名用例')).strip()
                if name and name != '未命名用例':
                    cases.append({
                        'title': title,
                        'module_name': module_name,
                        'function_name': function_name,
                        'name': name,
                        'priority': priority,
                        'precondition': str(row.get('precondition', '')).strip(),
                        'steps': steps_text,
                        'expected': expected_text,
                    })
            
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
            
            column_mapping = {
                '需求名称': 'title',
                '模块名称': 'module_name',
                '功能点名称': 'function_name',
                '功能模块': 'module_name',
                '用例名称': 'name',
                '优先级': 'priority',
                '前置条件': 'precondition',
                '测试步骤': 'steps',
                '操作步骤': 'steps',
                '预期结果': 'expected',
            }
            df.columns = [column_mapping.get(col, col) for col in df.columns]
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
                raw_steps = row.get('steps', '')
                raw_expected = row.get('expected', '')
                steps_list = split_lines(raw_steps, 'step')
                expected_list = split_lines(raw_expected, 'expected')
                if steps_list or expected_list:
                    steps_text = '\n'.join(f'{i+1}. {s}' for i, s in enumerate(steps_list)) if steps_list else ''
                    expected_text = '\n'.join(expected_list) if expected_list else ''
                else:
                    test_steps = excel_importer._parse_test_steps(raw_steps)
                    steps_text = '\n'.join(f'{i+1}. {(s.get("step") or "").strip()}' for i, s in enumerate(test_steps))
                    expected_text = '\n'.join((s.get('expected_result') or '').strip() for s in test_steps)

                priority = excel_importer._parse_priority(row.get('priority', 'P2'))
                name = str(row.get('name', '未命名用例')).strip()
                if name and name != '未命名用例':
                    cases.append({
                        'title': str(row.get('title', '')).strip(),
                        'module_name': str(row.get('module_name', '')).strip(),
                        'function_name': str(row.get('function_name', '')).strip(),
                        'name': name,
                        'priority': priority,
                        'precondition': str(row.get('precondition', '')).strip(),
                        'steps': steps_text,
                        'expected': expected_text,
                    })
            
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
