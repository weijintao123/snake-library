# 蛇类图库

网页：https://weijintao123.github.io/snake-library/

截至2026-10-19，152个既有物种目录中共有1147张内容SHA-256不重复的照片。本次从北京时间2026-10-18 13:42:49接续检查到2026-10-19 16:12:05，扫描50条，9条在窗口内，新增6张；3条新存疑内容及11条历史待处理项保留重试。详细结果：`docs/topic_sync_report.json`。

只追加话题中的蛇照片；先视觉核验，再按站点物种ID、学名、中文名保守匹配。站点物种标签不代表专家鉴定；存疑内容不误归档。规范化URL与内容SHA-256双重去重，既有照片不覆盖、不删除。

使用 `skills/snake-topics-daily/SKILL.md` 每日更新。Python3.12及Pillow环境中，`python scripts/sync_catalog.py` 从上次成功断点生成本次待审队列；核验后将记录标记 `visual_verified: true` 写入 `scripts/pending_topic_photos.json`，运行 `python scripts/sync_catalog.py --pending-only` 导入。发现接口需要安全配置环境变量 `SNAKE_TOPIC_TOKEN`；不要把凭据写进文件或聊天。

GitHub Actions计划为北京时间09:00，实际可能延迟。推送时导入已核验记录并部署Pages；定时发现缺少Secret或有新照片待核验时明确报告未完成，并保留待审artifact。浏览器登录不能替代仓库Secret。Skill本身不包含调度器。

验证：`python skills/snake-topics-daily/scripts/test_sync.py`。本次重复导入新增0张。指定窗口外的中断期尚未补抓，不因此推进完整历史截止点。

默认接续断点保存在 `docs/topic_sync_state.json`；当前初始值为北京时间2026-10-18 13:42:49。每次发布核验成功后才推进，失败重试不跳过时间段；历史未解决项保留到retry_topics并在后续运行一并补抓。只有明确要求补抓固定天数时使用--days。

每次手动更新先打开肥猫识蛇并核验当前登录。152种为初始目录数量；可靠确认的新增蛇种自动创建“学名--中文名--毒性”目录并追加物种表，网页数量动态变化。无法确认的新种保留待核验，毒性缺少依据时标注“毒性待核实”。
