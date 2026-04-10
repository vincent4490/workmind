/**
 * 创建人下拉展示：姓名与登录名都带上，便于用中文名或英文账号搜索。
 * @param {{ id?: number, name?: string, username?: string }} u
 */
export function formatCreatorOptionLabel(u) {
    if (!u) return ''
    const name = (u.name || '').trim()
    const login = (u.username || '').trim()
    if (name && login && name !== login) return `${name}（${login}）`
    return name || login || String(u.id ?? '')
}
