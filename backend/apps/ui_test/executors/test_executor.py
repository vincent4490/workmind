# -*- coding: utf-8 -*-
"""
测试执行器 - 整合 Slot Game Automation 的测试执行逻辑
"""
import os
import sys
import subprocess
from typing import Optional, List, Dict, Any
from loguru import logger

from ..constants import TestType


class UiTestExecutor:
    """UI测试执行器，封装 pytest 执行逻辑"""
    
    def __init__(self, base_path: Optional[str] = None):
        """
        初始化测试执行器
        """
        if base_path is None:
            # 获取 Django 项目的 backend 目录
            self.base_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            logger.debug(f"UiTestExecutor 初始化 - base_path: {self.base_path}")
        else:
            self.base_path = base_path
            logger.debug(f"UiTestExecutor 初始化 - base_path (provided): {self.base_path}")
        
        if not os.path.exists(self.base_path):
            raise ValueError(f"测试项目路径不存在: {self.base_path}")
        
        self._current_process: Optional[subprocess.Popen] = None
    
    def _get_project_paths(self):
        """获取项目路径（backend, apps）"""
        executors_dir = os.path.dirname(os.path.abspath(__file__))
        ui_test_dir = os.path.dirname(executors_dir)
        apps_dir = os.path.dirname(ui_test_dir)
        backend_dir = os.path.dirname(apps_dir)
        return backend_dir, apps_dir

    def _setup_sys_path(self, backend_dir: str, apps_dir: str):
        """设置 sys.path，确保 apps 目录优先级最高"""
        if backend_dir in sys.path:
            sys.path.remove(backend_dir)
        
        if apps_dir in sys.path:
            sys.path.remove(apps_dir)
        sys.path.insert(0, apps_dir)
        
        if 'backend' in sys.modules:
            del sys.modules['backend']

    def _build_pythonpath(self, backend_dir: str, apps_dir: str) -> str:
        """构建 PYTHONPATH 环境变量"""
        python_path_parts = []
        for path in [backend_dir, apps_dir]:
            if os.path.exists(path):
                python_path_parts.append(path)
        
        for p in sys.path:
            if p and os.path.exists(p) and p not in python_path_parts:
                if 'site-packages' in p or not p.endswith('.exe'):
                    python_path_parts.append(p)
        
        return os.pathsep.join(python_path_parts)
    
    def run_tests(
        self,
        device_id: Optional[str] = None,
        package_name: Optional[str] = None,
        test_id: Optional[str] = None,
        user_id: Optional[str] = None,
        password: Optional[str] = None,
        execution_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        运行UI测试用例并生成报告
        """
        logger.info(f"开始执行UI测试: test_id={test_id}")
        
        original_cwd = os.getcwd()
        try:
            backend_dir, apps_dir = self._get_project_paths()
            os.chdir(apps_dir)
            
            # 环境变量准备
            env = os.environ.copy()
            env['PYTHONPATH'] = self._build_pythonpath(backend_dir, apps_dir)
            env['DJANGO_SETTINGS_MODULE'] = os.environ.get('DJANGO_SETTINGS_MODULE', 'backend.settings')
            if execution_id:
                env['UI_FLOW_EXECUTION_ID'] = str(execution_id)
            # 传递测试工程师环境变量到子进程
            if 'TEST_ENGINEER' in os.environ:
                env['TEST_ENGINEER'] = os.environ['TEST_ENGINEER']

            # 构建 pytest 参数
            pytest_args = [
                sys.executable, '-m', 'pytest',
                '--rootdir', apps_dir,
                '-s', '-v',
                '--alluredir', self._get_allure_results_dir(test_id),
            ]
            
            if device_id: pytest_args.extend(['--device-id', device_id])
            if package_name: pytest_args.extend(['--package-name', package_name])
            if user_id and password: pytest_args.extend(['--user-id', user_id, '--password', password])
            
            # 指定 conftest.py 所在目录
            pytest_args.append('ui_test')
            
            logger.info(f"执行命令: {' '.join(pytest_args)}")
            
            process = subprocess.Popen(
                pytest_args,
                cwd=apps_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=1,
                env=env
            )
            self._current_process = process
            
            output_lines = []
            important_patterns = ['PASSED', 'FAILED', 'ERROR', 'SKIPPED', 'collected', 'passed', 'failed', 'skipped']
            
            if process.stdout:
                for line in process.stdout:
                    line = line.rstrip()
                    if line:
                        output_lines.append(line)
                        if any(pattern in line for pattern in important_patterns):
                            logger.info(f"[pytest] {line}")
            
            exit_code = process.wait()
            self._current_process = None
            logger.info(f"pytest 执行完成，退出码: {exit_code}")
            
            if exit_code != 0:
                logger.warning("pytest 执行失败，查看最后输出...")
            
            test_results = self._parse_allure_results(test_id)
            
            # 同步生成报告（确保报告路径能被保存）
            report_path = self._generate_allure_report(test_id)
            
            return {
                'success': exit_code == 0,
                'exit_code': exit_code,
                'report_path': report_path,
                'test_results': test_results,
            }
            
        except Exception as e:
            logger.error(f"执行测试失败: {e}")
            return {'success': False, 'error': str(e)}
        finally:
            os.chdir(original_cwd)
    
    def _get_allure_results_dir(self, test_id: Optional[str] = None) -> str:
        results_base = os.path.join(self.base_path, 'ui_test', 'allure-results')
        if test_id:
            return os.path.join(results_base, f"allure-results-{test_id}")
        return results_base
    
    def _generate_allure_report(self, test_id: Optional[str] = None) -> Optional[str]:
        try:
            allure_results_dir = self._get_allure_results_dir(test_id)
            reports_base = os.path.join(self.base_path, 'ui_test', 'allure-reports')
            report_dir = os.path.join(reports_base, f"allure-reports-{test_id}" if test_id else "allure-report")
            
            os.makedirs(report_dir, exist_ok=True)
            allure_path = self._find_allure_command()
            
            if not allure_path:
                logger.warning("未找到 Allure 命令，跳过报告生成")
                return None
            
            cmd = [allure_path, 'generate', allure_results_dir, '-o', report_dir, '--clean']
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            
            if result.returncode == 0:
                logger.info(f"Allure 报告生成成功: {report_dir}")
                return report_dir
            return None
        except Exception as e:
            logger.error(f"生成 Allure 报告失败: {e}")
            return None
    
    def _find_allure_command(self) -> Optional[str]:
        import platform
        if platform.system() == 'Windows':
            for p in [r'D:\Program Files\allure-2.34.1\bin\allure.bat', r'C:\Program Files\allure-2.34.1\bin\allure.bat']:
                if os.path.exists(p): return p
        return 'allure'
    
    def _calculate_test_progress(self, test_id: Optional[str] = None, is_running: bool = True) -> int:
        try:
            import glob
            allure_results_dir = self._get_allure_results_dir(test_id)
            if not os.path.exists(allure_results_dir): return 1
            
            result_files = glob.glob(os.path.join(allure_results_dir, '*-result.json'))
            current_files = len(result_files)
            if current_files == 0: return 1
            
            total_cases = current_files + 1 if is_running else max(current_files, 1)
            progress = int((current_files / total_cases) * 100)
            return max(1, min(progress, 100))
        except Exception:
            return 1
    
    def _parse_allure_results(self, test_id: Optional[str] = None) -> dict:
        try:
            import json
            import glob
            allure_results_dir = self._get_allure_results_dir(test_id)
            if not os.path.exists(allure_results_dir):
                return {'total': 0, 'passed': 0, 'failed': 0, 'skipped': 0, 'broken': 0}
            
            result_files = glob.glob(os.path.join(allure_results_dir, '*-result.json'))
            stats = {'total': 0, 'passed': 0, 'failed': 0, 'skipped': 0, 'broken': 0, 'test_cases': []}
            
            for rf in result_files:
                try:
                    with open(rf, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    stats['total'] += 1
                    status = data.get('status', 'unknown').lower()
                    if status in stats: stats[status] += 1
                    
                    stats['test_cases'].append({
                        'name': data.get('name', ''),
                        'status': status,
                        'duration': data.get('stop', 0) - data.get('start', 0),
                        'error_message': data.get('statusDetails', {}).get('message', '')
                    })
                except Exception: continue
            return stats
        except Exception:
            return {'total': 0, 'passed': 0, 'failed': 0, 'skipped': 0, 'broken': 0}
