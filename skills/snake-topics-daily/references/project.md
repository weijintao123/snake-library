# 项目与恢复

- 仓库：https://github.com/weijintao123/snake-library （默认分支main）
- 图库：https://weijintao123.github.io/snake-library/
- 来源：https://snake.pictureknow.com/topics
- 原迁移包SHA-256：c14aa8ff5065a6411d64ab0ee8e55164670b967873dd2310643206b67e54b51c。
- 2026-10-18检查时线上基线：c77eb6f9c30b4a24a2efebde5bd3fc410765522e、1094条索引、152个物种。此为历史检查点，后续应重读线上。
- 当日运行39100686559虽成功，但日志显示SNAKE_TOPIC_TOKEN未配置；只重新导入42条旧待办，新增0。不能因此认为10月8日后已检查完。
- 基线未包含topic_sync_state.json；恢复时不能默认只抓昨天而漏掉中断期。升级脚本在无状态时扫描当前可返回集合；站点可见历史不足时明确报告无法补齐。

## 可见卡片导入

先检查卡片DOM结构再提取；2026-10-18卡片为 `.item-container`，原图元素为 `img.ant-image-img`，class中 `image-<ID>` 提供话题ID，蛇种链接 `/snake?id=<ID>` 提供物种ID，正文含学名、中文名、毒性。排除头像、logo、二维码和评论者图片。只读取DOM，不检查React内部状态、Cookie或localStorage。

```json
{"source":"https://snake.pictureknow.com/topics","coverage":"browser-visible-only","topics":[{"uniqueId":"实际话题ID","img":"实际原图URL","snakeId":"站点物种ID","sciName":"实际学名","cnName":"实际中文名"}]}
```

无发布时间不捏造createTime。`--pending-only`不推进API截止点。脚本只能检查格式和匹配，调用前必须视觉排除非蛇或无法确认内容。

## 升级与发布

`assets/sync_catalog.py`修复：缺凭据显式失败、公开客户端的timestamp/signature参数、最近N天完整分页、发现与视觉复核分离、未复核记录不得导入、跨目录内容去重先于写入、已知URL可补本地镜像、真实图片格式扩展名、物种字段冲突拒绝归档、跳过项报告。请求签名前缀来自网站公开JS，并非用户密码或登录令牌；修改接口时重新核对客户端。可在已登录浏览器中直接导航签名API URL，然后只提取响应DOM的图片/物种/时间字段；不要导出Cookie、读取React内部状态或通过脚本执行浏览器网络请求。

安装Pillow后运行附带 `scripts/test_sync.py`。原图不可读时允许使用网站仅格式转换的全尺寸WebP，保留原图地址及实际下载地址；若两者均不可读则记录待重试。2026-10-18最近72小时检查100条，其中65条在窗口内；47条归档、18条跳过（7条非蛇、6条内容/物种存疑、5条原图及网页版本均不可访问），总数1141。此为当日历史记录。

工作流：推送仅导入已核验待办并部署；定时/手动发现需Secret，缺失则失败；新候选保存为Actions待审artifact并明确提示复核，不能声称已自动完成归档。没有新候选则可正常部署。Skill支持用户每日调用，不会自行创造调度任务。移除旧的历史删除步骤，保留既有图库。

任何GitHub Secret只能由用户通过GitHub安全设置维护。本地Python若是macOS占位程序且报缺Xcode，用Codex工作区依赖工具定位随附Python；不要求为本技能安装Xcode。
