# 蛇类资料库（云端版）

GitHub Actions 每天北京时间 09:00 只读取 `snake.pictureknow.com/topics` 的话题列表，并将话题中新增的蛇照片追加到 `docs/photos/topics/`。它不会抓取“剧毒蛇、微毒蛇、无毒蛇”目录或蛇种详情页。

首次运行采集前一个北京时间 09:00 至当天 09:00 的内容；以后从上次成功截止点继续，任务延迟或失败后不会漏过时间段。图片以 SHA-256 内容哈希命名，`docs/topic_photo_index.json` 同时按规范化原始地址和内容哈希去重，因此同图不同 URL 也只保存一次。网页由 GitHub Pages 部署。

`docs/photos/` 是仓库内本地副本，推送后同时成为 GitHub/Pages 云端副本。若还需镜像到独立的本机归档目录，运行同步前设置 `SNAKE_LOCAL_PHOTO_ROOT`；任一副本写入失败时索引不会提交，下次运行会以相同哈希路径幂等重试。

话题接口要求登录。请把站点登录令牌保存为 GitHub Actions 仓库 Secret `SNAKE_TOPIC_TOKEN`；本机测试则设置同名环境变量。令牌只作为请求 Cookie 使用，不会写入文件、日志或索引。话题专用索引为 `docs/topic_photo_index.json`。

基础校验：`python -m unittest discover -s tests -v`。

## 152 种蛇目录

`docs/photos/` 下固定建立 152 个以“学名--中文名--毒性”命名的目录。话题照片只有在蛇种 ID、学名或中文名唯一匹配时才进入对应目录；未能可靠匹配的内容不会误归类。Git 使用各目录内的 `.gitkeep` 保留尚无照片的空目录。

