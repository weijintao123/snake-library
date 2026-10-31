# 蛇类图库

网页：https://weijintao123.github.io/snake-library/

截至2026-11-01，现有152个物种目录共有1198张内容SHA-256不重复的照片。本次从北京时间2026-10-23 09:31:22接续至2026-11-01 00:06:24，完整扫描4页200条话题，其中186条在窗口内；并重试51条历史记录。新增27张、内容哈希重复0张、排除2条非蛇内容。208条保留重试，其中183条原图及全尺寸WebP均返回403，25条图片内容或物种标签存疑。暂无可靠新蛇种。详细结果：`docs/topic_sync_report.json`。

只追加话题中的蛇照片；先视觉核验，再按站点物种ID、学名、中文名保守匹配。站点物种标签不代表专家鉴定；存疑内容不误归档。规范化URL与内容SHA-256双重去重，既有照片不覆盖、不删除。

使用 `skills/snake-topics-daily/SKILL.md` 每日更新。Python3.12及Pillow环境中，`python scripts/sync_catalog.py` 从上次成功断点生成本次待审队列；核验后将记录标记 `visual_verified: true` 写入 `scripts/pending_topic_photos.json`，运行 `python scripts/sync_catalog.py --pending-only` 导入。发现接口需要安全配置环境变量 `SNAKE_TOPIC_TOKEN`；不要把凭据写进文件或聊天。

GitHub Actions计划为北京时间09:00，实际可能延迟。推送时导入已核验记录并部署Pages；定时发现缺少Secret或有新照片待核验时明确报告未完成，并保留待审artifact。浏览器登录不能替代仓库Secret。Skill本身不包含调度器。

验证：`python skills/snake-topics-daily/scripts/test_sync.py`。本次重复导入新增0张。下载失败和存疑项保留到retry_topics，下次继续重试。

默认接续断点保存在 `docs/topic_sync_state.json`；首次恢复值为北京时间2026-10-18 13:42:49，当前成功截止点以该状态文件为准。每次发布核验成功后才推进，失败重试不跳过时间段；历史未解决项保留到retry_topics并在后续运行一并补抓。只有明确要求补抓固定天数时使用--days。

每次手动更新先打开肥猫识蛇并核验当前登录。152种为初始目录数量；可靠确认的新增蛇种自动创建“学名--中文名--毒性”目录并追加物种表，网页数量动态变化。无法确认的新种保留待核验，毒性缺少依据时标注“毒性待核实”。

