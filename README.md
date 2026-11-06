# 蛇类图库

网页：https://weijintao123.github.io/snake-library/

截至2026-11-06，图库共152种、1232张唯一蛇类照片。原24张待核验蛇图已按用户明确核验的结果整合进现有蛇种目录，不新增重复目录；当前待核验图片为0张。旧待核验目录及其重复副本已清理，来源、哈希及用户核验记录保留在图片索引中。本次仅整理既有照片，不推进来源发现的成功断点。

只追加话题中的蛇照片；先视觉核验，再按站点物种ID、学名、中文名保守匹配。站点物种标签不代表专家鉴定；存疑内容不误归档。规范化URL与内容SHA-256双重去重，既有照片不覆盖、不删除。

使用 `skills/snake-topics-daily/SKILL.md` 每日更新。Python3.12及Pillow环境中，`python scripts/sync_catalog.py` 从上次成功断点生成本次待审队列；核验后将记录标记 `visual_verified: true` 写入 `scripts/pending_topic_photos.json`，运行 `python scripts/sync_catalog.py --pending-only` 导入。发现接口需要安全配置环境变量 `SNAKE_TOPIC_TOKEN`；不要把凭据写进文件或聊天。

每日完整更新由Codex本聊天定时任务在北京时间10:00执行；原GitHub 09:00计划已移除，避免重复。推送时导入已核验记录并部署Pages；手动触发Actions发现时，缺少Secret或有新照片待核验会明确报告未完成，并保留待审artifact。浏览器登录不能替代仓库Secret。Skill本身不包含调度器。

验证：`python skills/snake-topics-daily/scripts/test_sync.py`。本次重复导入新增0张。下载失败和存疑项保留到retry_topics，下次继续重试。

默认接续断点保存在 `docs/topic_sync_state.json`；首次恢复值为北京时间2026-10-18 13:42:49，当前成功截止点以该状态文件为准。每次发布核验成功后才推进，失败重试不跳过时间段；历史未解决项保留到retry_topics并在后续运行一并补抓。只有明确要求补抓固定天数时使用--days。

每次手动更新先打开肥猫识蛇并核验当前登录。152种为初始目录数量；可靠确认的新增蛇种自动创建“学名--中文名--毒性”目录并追加物种表，网页数量动态变化。无法确认的新种保留待核验，毒性缺少依据时标注“毒性待核实”。



技能在线安装：在另一台电脑的Codex发送「使用 $skill-installer 安装 https://github.com/weijintao123/snake-library/tree/skill-package/skills/snake-topics-daily」。安装后下一轮可调用；新电脑需重新登录Codex、GitHub和肥猫识蛇。离线包：[snake-topics-daily.zip](https://weijintao123.github.io/snake-library/downloads/snake-topics-daily.zip)。本轮复查至北京时间2026-11-01 00:31:05，未发现发布后新增话题；183条失败图再次尝试仍不可读取。
