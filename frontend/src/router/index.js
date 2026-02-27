import { createRouter, createWebHistory } from "vue-router";
import Login from "@/pages/login/Login";
import Home from "@/pages/home/Home";
import Dashboard from "@/pages/workmind/dashboard/Dashboard";
import DeviceManagement from "@/pages/workmind/app_ui/DeviceManagement";
import AppPackageManagement from "@/pages/workmind/app_ui/AppPackageManagement";
import ElementManagement from "@/pages/workmind/app_ui/ElementManagement";
import UiTestSceneBuilder from "@/pages/workmind/app_ui/UiTestSceneBuilder";
import UiFlowCaseList from "@/pages/workmind/app_ui/UiFlowCaseList";
import RequirementManagement from "@/pages/workmind/app_ui/RequirementManagement";
import FunctionalTestCaseManagement from "@/pages/workmind/app_ui/FunctionalTestCaseManagement";
import TestPlanManagement from "@/pages/workmind/app_ui/TestPlanManagement";
import TestPlanExecute from "@/pages/workmind/app_ui/TestPlanExecute";
import AiTestcaseGenerator from "@/pages/workmind/ai_testcase/AiTestcaseGenerator";
import Redirect from "@/pages/redirect/Redirect";

const router = createRouter({
    history: createWebHistory(),
    routes: [
        {
            path: "/",
            redirect: "/workmind/login"
        },
        {
            path: "/workmind/login",
            name: "Login",
            component: Login,
            meta: {
                title: "WorkMind测试平台"
            }
        },
        {
            path: "/workmind",
            name: "Index",
            component: Home,
            meta: {
                title: "首页",
                requireAuth: true
            },
            children: [
                {
                    path: "",
                    name: "IndexDefault",
                    redirect: { name: "Dashboard" }
                },
                {
                    path: "redirect/:path(.*)",
                    component: Redirect,
                    meta: { hidden: true }
                },
                {
                    name: "Dashboard",
                    path: "dashboard",
                    component: Dashboard,
                    meta: {
                        title: "首页",
                        requireAuth: true,
                        affix: true // 固定标签，不可关闭
                    }
                },
                {
                    name: "DeviceManagement",
                    path: "device_management",
                    component: DeviceManagement,
                    meta: {
                        title: "设备管理",
                        requireAuth: true
                    }
                },
                {
                    name: "AppPackageManagement",
                    path: "app_package_management",
                    component: AppPackageManagement,
                    meta: {
                        title: "应用包名管理",
                        requireAuth: true
                    }
                },
                {
                    name: "ElementManagement",
                    path: "element_management",
                    component: ElementManagement,
                    meta: {
                        title: "元素管理",
                        requireAuth: true
                    }
                },
                {
                    name: "UiTestSceneBuilder",
                    path: "ui_test_scene",
                    component: UiTestSceneBuilder,
                    meta: {
                        title: "UI场景编排",
                        requireAuth: true
                    }
                },
                {
                    name: "UiFlowCaseList",
                    path: "ui_flow_cases",
                    component: UiFlowCaseList,
                    meta: {
                        title: "UI场景用例列表",
                        requireAuth: true
                    }
                },
                {
                    name: "RequirementManagement",
                    path: "functional_requirement",
                    component: RequirementManagement,
                    meta: {
                        title: "需求管理",
                        requireAuth: true
                    }
                },
                {
                    name: "FunctionalTestCaseManagement",
                    path: "functional_test_case",
                    component: FunctionalTestCaseManagement,
                    meta: {
                        title: "功能测试用例管理",
                        requireAuth: true
                    }
                },
                {
                    name: "TestPlanManagement",
                    path: "test_plan",
                    component: TestPlanManagement,
                    meta: {
                        title: "测试计划管理",
                        requireAuth: true
                    }
                },
                {
                    name: "TestPlanExecute",
                    path: "test_plan_execute/:planId",
                    component: TestPlanExecute,
                    meta: {
                        title: "执行测试计划",
                        requireAuth: true
                    }
                },
                {
                    name: "AiTestcaseGenerator",
                    path: "ai_testcase",
                    component: AiTestcaseGenerator,
                    meta: {
                        title: "AI用例智能体",
                        requireAuth: true
                    }
                },
            ]
        }
    ]
})

export default router
