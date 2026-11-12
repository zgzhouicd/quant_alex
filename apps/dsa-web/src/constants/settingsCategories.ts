/** 设置页不向普通 Web 用户暴露的分类（后端仍可通过 .env 配置）。 */
export const WEB_HIDDEN_SETTINGS_CATEGORIES = new Set<string>(['notification']);

/** 已从默认产品路径移除、仅 .env 保留的遗留键。 */
export const WEB_HIDDEN_SETTINGS_KEYS = new Set<string>([
  'TUSHARE_TOKEN',
  'TICKFLOW_API_KEY',
]);
