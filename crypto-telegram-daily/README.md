# crypto-telegram-daily

用 GitHub Actions 每天定时把「恐慌指数 + 爆量 Meme 观察 + 热门叙事」推送到 Telegram 频道。

## 1) Telegram 准备
1. 用 @BotFather 创建一个 Bot，拿到 `TELEGRAM_BOT_TOKEN`
2. 创建频道，把 Bot 设为管理员（允许发消息）
3. `TELEGRAM_CHAT_ID`：
   - 公共频道：直接填 `@your_channel_username`
   - 私密频道：需要数值 chat_id（通常是 `-100xxxxxxxxxx`）。方法：
     - 先让机器人给你私聊发一条消息
     - 浏览器打开：`https://api.telegram.org/bot<你的TOKEN>/getUpdates`
     - 在返回 JSON 里找 `chat.id`

> 提醒：不要把 token 写进代码，放到 GitHub Secrets 里。

## 2) GitHub Secrets
在仓库 Settings → Secrets and variables → Actions → New repository secret 添加：
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

## 3) 修改关注列表
编辑 `config.yaml` 的 `watchlist`，填你关注的 token 地址即可。
- Solana token：填 mint 地址（base58）
- EVM 链：填 0x 开头合约地址

编辑 `hot_topics.yaml` 可以每天补“刷屏叙事”。

## 4) 定时执行
`.github/workflows/daily.yml` 已设置北京时间 10:00（UTC 02:00）运行。
你也可以在 Actions 页面手动点击运行（workflow_dispatch）。

## 5) 本地测试
```bash
python -m venv .venv
source .venv/bin/activate  # Windows 用 .venv\Scripts\activate
pip install -r requirements.txt

export TELEGRAM_BOT_TOKEN="..."
export TELEGRAM_CHAT_ID="@your_channel"
python src/main.py
```