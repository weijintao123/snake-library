# 项目与恢复

- 仓库：https://github.com/weijintao123/snake-library （默认分支main）
- 图库：https://weijintao123.github.io/snake-library/
- 来源：https://snake.pictureknow.com/topics
- 原迁移包SHA-256：c14aa8ff5065a6411d64ab0ee8e55164670b967873dd2310643206b67e54b51c。
- 2026-10-18检查时线上基线：c77eb6f9c30b4a24a2efebde5bd3fc410765522e、1094条索引、152个物种。此为历史检查点，后续应重读线上。
- 当日运行39100686559虽成功，但日志显示SNAKE_TOPIC_TOKEN未配置；只重新导入42条旧待办，新增0。不能因此认为10月8日后已检查完。
- 基线未包含topic_sync_state.json；恢复时不能默认只抓昨天而漏掉中断期。现已从核验过的发布窗口结束时间恢复初始断点；如果状态文件丢失，先从发布证据恢复，不默认最近三天。

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


## 持久化接续（当前默认）

`docs/topic_sync_state.json` 保存 `last_successful_cutoff`、`last_verified_data_commit`、`last_verified_deployment`、`verified_image_count`、`retry_topics` 和 `excluded_topic_ids`。首次种子来自2026-10-18已核验发布，截止北京时间13:42:49；7条非蛇已排除，11条未解决内容带原始地址保留重试。断点表示该窗口已经逐条处理，未解决照片仍须通过重试清单继续补充，不表示所有源站照片均已下载。

默认 `python scripts/sync_catalog.py`；显式补抓才用 `--since 2026-10-18T13:42:49+08:00` 或 `--days N`。`scripts/topic_review_queue.json` 记录 `base_cutoff`、冻结的起止时间及合并后的候选。发现和 `--pending-only` 均不写成功断点，由执行Skill的Codex在实际核验部署后更新。

完成一次运行时，核对当前远端断点仍等于本轮 `base_cutoff`；如已被其他运行推进，重新合并状态和重试清单，不覆盖新状态。只将当前覆盖窗口的结束时间提交为新断点；历史补抓不倒退已成功断点。保留完整待重试条目；导入成功或确定非蛇后移除对应重试项，并更新排除ID。没有新增但检查完整时，也提交有意义的断点变化。状态提交失败不影响照片已发布事实，下一次按旧断点去重重试。


## 每次登录与新增蛇种（2026-10-19更新）

每次手动执行都先打开并刷新肥猫识蛇，核验当前已登录状态及话题读取成功；需要登录时在站点正常登录，不把凭据交给聊天或文件。仅有本机/Actions环境变量不能代替本次浏览器登录检查。登录仍有效时刷新确认即可；用户明确要求重新登录时执行正常重新登录。登录失败不推进断点。

物种表可以超过152项。新物种须有本次核对过的站点详情页、稳定物种ID、明确学名与中文名；检查既有记录的同物异名、中文同名和改名，不能仅因匹配失败就自动认定新种。话题的AI标注本身不足以给新增物种确认身份。确认后在已视觉核验的话题中增加：

```json
"new_species": {
  "verified": true,
  "site_id": "与话题snakeId一致的已核对ID",
  "scientific_name": "与话题sciName一致的已核对学名",
  "chinese_name": "与话题cnName一致的已核对中文名",
  "toxicity": "毒性待核实",
  "source_url": "https://snake.pictureknow.com/snake?id=已核对ID"
}
```

`verified`由Codex读取并核对来源后设置，不从未经审核的话题响应照抄。毒性依据可靠来源填写剧毒/微毒/无毒，缺失则毒性待核实。脚本按“学名--中文名--毒性”建目录、保留.gitkeep并追加species_catalog，total_species动态计算；重复运行不重复建目录。跨种相同图片仍按全局SHA-256只存一份，新种目录可为空但物种记录保留。图片下载失败时不落盘新物种表，重试保持幂等。提交时包含新增目录、species_catalog和照片索引；网页标题与数量随目录动态显示，禁止写死152。既有目录不重命名、不删除，不改变已记录毒性。
