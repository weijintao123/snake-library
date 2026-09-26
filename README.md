# 蛇类资料库（云端版）

公开网页展示中国蛇类的当前照片、中文名、学名与毒性。GitHub Actions 每天北京时间 09:00 从 `snake.pictureknow.com` 的公开目录和详情页重新生成 `docs/catalog.json`，并将当前照片镜像到 `docs/photos/`。

每次同步都以新镜像替换旧镜像：源站已删除的照片会随之从云端资料库移除，避免重复占用空间。网页由 GitHub Pages 部署。
