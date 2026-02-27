/**
 * 全局属性 Composable
 * 方便访问全局注册的属性和方法
 */
import { getCurrentInstance } from 'vue'

export function useGlobalProperties() {
  const instance = getCurrentInstance()
  const globalProperties = instance?.appContext.config.globalProperties
  
  return {
    $api: globalProperties?.$api,
    $filters: globalProperties?.$filters,
    setLocalValue: globalProperties?.setLocalValue,
    getLocalValue: globalProperties?.getLocalValue
  }
}
