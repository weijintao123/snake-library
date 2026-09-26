# 蛇类资料库（云端版）

公开网页展示中国蛇类的照片、中文名、学名与毒性。GitHub Actions 每天北京时间 09:00 从 `snake.pictureknow.com` 的公开目录和详情页更新 `docs/catalog.json`，并将新出现的照片追加到 `docs/photos/`。

已保存的历史图片不会被替换或删除；即使源站后来不再展示，仍会保留在资料库。`docs/photo_index.json` 用于按图片原始地址去重。网页由 GitHub Pages 部署。
