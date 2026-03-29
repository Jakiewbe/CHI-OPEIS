# 测试说明

## 运行方式

```powershell
$env:QT_QPA_PLATFORM="offscreen"
.\.venv\Scripts\pytest -q
```

## 当前覆盖

- `chi_generator` 新 domain service 的脚本生成
- 固定电压 / 固定时间 / 脉冲场景
- 默认 OCV、通用头尾命令、`CC / EIS` 命名契约
- `mAh/g + mg` 的 1C 换算
- dense EIS / OCV 过密 / IMP 间歇化告警
- GUI 离屏实例化
- `_scenario` 兼容属性
- `opeis_master.domain.*` 旧契约兼容

## 建议后续补充

- `预处理 + 正式测试` 的细粒度脚本断言
- `分阶段均匀时间点` 的更多边界测试
- GUI 字段高亮与显隐逻辑测试
