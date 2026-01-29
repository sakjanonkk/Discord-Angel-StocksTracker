import discord
from discord.ext import commands, tasks
import yfinance as yf
import feedparser 
import urllib.parse 
import os
from datetime import datetime
from dotenv import load_dotenv

# ---------------------------------------------------------
# ⚙️ CONFIG & SETUP
# ---------------------------------------------------------
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

# ตั้งค่าห้องที่จะให้แจ้งเตือน
STOCK_CHANNEL_ID = 1466556480395280424 

# Setup Bot
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# ---------------------------------------------------------
# 🛠️ HELPER FUNCTIONS (ฟังก์ชันช่วยทำงาน)
# ---------------------------------------------------------

def format_ticker_line(data, symbol):
    """ฟังก์ชันจัดรูปแบบราคา รองรับทั้งหุ้น, Crypto, Forex"""
    try:
        stock = data.tickers[symbol]
        info = stock.info
        
        # 1. ระบบหา "ราคาปัจจุบัน"
        price = info.get('currentPrice') or \
                info.get('regularMarketPrice') or \
                info.get('lastPrice') or \
                info.get('ask') 
        
        # 2. ระบบหา "ราคาปิดเมื่อวาน"
        prev_close = info.get('previousClose') or \
                     info.get('regularMarketPreviousClose')

        # --- UPDATE: ชื่อย่อสำหรับ Tradable ETFs & Indicators ---
        name_map = {
            "SPY": "S&P 500 (SPY) 🇺🇸",
            "QQQ": "Nasdaq 100 (QQQ) 💻",
            "TDEX.BK": "Thai SET50 (TDEX) 🇹🇭",
            
            # Indicators ใหม่
            "^TNX": "US 10Y Bond 🏦",
            "^VIX": "VIX (Fear Index) 😱",
            
            # ของเดิม
            "GC=F": "Gold 🥇", 
            "CL=F": "Crude Oil 🛢️",
            "BTC-USD": "Bitcoin ₿", 
            "ETH-USD": "Ethereum 💎",
            "USDTHB=X": "USD/THB 🇹🇭"
        }
        display_name = name_map.get(symbol, symbol)

        if price is None: 
            return f"⚠️ **{display_name}**: N/A (รอตลาดเปิด/Data Delay)"

        # คำนวณ % Change
        if prev_close and prev_close > 0:
            change = ((price - prev_close) / prev_close) * 100
        else:
            change = 0.0

        # เลือก Emoji
        if change > 0: arrow = "🟢"
        elif change < 0: arrow = "🔴"
        else: arrow = "⚪"
        
        # ถ้าเป็น Bond Yield หรือ VIX ไม่ต้องใส่เครื่องหมาย $ ด้านหน้า
        if symbol in ["^TNX", "^VIX"]:
            return f"{arrow} **{display_name}**: `{price:,.2f}` ({change:+.2f}%)"
        else:
            return f"{arrow} **{display_name}**: `${price:,.2f}` ({change:+.2f}%)"

    except Exception:
        return f"❌ {symbol}: Error"

async def get_stock_data():
    """ดึงข้อมูลราคาหุ้นและสินทรัพย์ทั้งหมด (ฉบับ Tradable ETFs + Market Health)"""
    
    # 1. กองทุน ETF ตลาด (ซื้อขายได้จริง!)
    ETFS = ["SPY", "QQQ", "TDEX.BK"] 
    
    # 2. Market Indicators (วัดชีพจรตลาด)
    INDICATORS = ["^TNX", "^VIX"]

    # 3. หุ้นเทค (Tech Stocks)
    STOCKS = ["NVDA", "TSLA", "AAPL", "MSFT", "AMZN", "GOOGL", "META"]
    
    # 4. สินทรัพย์อื่นๆ
    OTHERS = ["GC=F", "CL=F", "BTC-USD", "ETH-USD", "USDTHB=X"]
    
    # รวม Tickers
    all_tickers = ETFS + INDICATORS + STOCKS + OTHERS
    tickers_str = " ".join(all_tickers)
    
    try:
        data = yf.Tickers(tickers_str)
    except Exception as e:
        print(f"Error fetching data: {e}")
        return None

    embed = discord.Embed(
        title="📊 Global Market Watch",
        description="*Tradable Assets & Market Health*",
        color=discord.Color.dark_theme(),
        timestamp=datetime.now()
    )

    # Helper function
    def build_section(ticker_list, title, emoji_header):
        text = ""
        for symbol in ticker_list:
            line = format_ticker_line(data, symbol)
            if line: text += line + "\n"
        if text:
            embed.add_field(name=f"{emoji_header} {title}", value=text, inline=False)

    # สร้างหมวดหมู่
    build_section(ETFS, "Market ETFs (Tradeable)", "🌎")
    build_section(INDICATORS, "Market Health (Bond & VIX)", "🏥") # หมวดใหม่!
    build_section(STOCKS, "US Tech Giants", "🇺🇸")
    build_section(OTHERS, "Gold, Oil & Crypto", "🏆")
            
    embed.set_footer(text="Bot by BEERs Finance • Data by Yahoo")
    return embed

# ---------------------------------------------------------
# 💬 COMMANDS (คำสั่ง)
# ---------------------------------------------------------

@bot.command()
async def angel(ctx):
    """เช็คราคาหุ้นทันที (!angel)"""
    async with ctx.typing():
        embed = await get_stock_data()
        if embed: await ctx.send(embed=embed)
        else: await ctx.send("❌ ดึงข้อมูลล้มเหลว ลองใหม่ครับ")

@bot.command()
async def news(ctx, symbol: str = "Stock Market"):
    """เช็คข่าวจาก Google News (!news [ชื่อหุ้น])"""
    
    # ✅ แก้ไข: ใช้ urllib.parse.quote เพื่อแปลงเว้นวรรคเป็น %20
    query_text = f"{symbol} stock news"
    encoded_query = urllib.parse.quote(query_text)
    
    rss_url = f"https://news.google.com/rss/search?q={encoded_query}&hl=en-US&gl=US&ceid=US:en"
    
    msg = await ctx.send(f"🔄 กำลังดึงข่าวล่าสุดของ **{symbol.upper()}**...")
    
    try:
        feed = feedparser.parse(rss_url)
        
        if not feed.entries:
            await msg.edit(content=f"❌ ไม่พบข่าวของ {symbol} ครับ")
            return

        embed = discord.Embed(
            title=f"📰 Google News: {symbol.upper()}",
            description="อัปเดตข่าวล่าสุด",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )

        # ดึง 5 ข่าวแรก
        for entry in feed.entries[:5]:
            title = entry.title
            link = entry.link
            published = entry.published_parsed
            
            time_str = ""
            if published:
                dt = datetime(*published[:6])
                time_str = f"• <t:{int(dt.timestamp())}:R>"

            embed.add_field(
                name=f"🔹 {title}",
                value=f"{time_str}\n[👉 อ่านข่าวฉบับเต็ม]({link})",
                inline=False
            )
            
        await msg.delete()
        await ctx.send(embed=embed)
        
    except Exception as e:
        await msg.edit(content=f"❌ Error: {e}")

@bot.command()
async def cal(ctx, symbol: str, amount: float):
    """คำนวณมูลค่าพอร์ต (!cal NVDA 10)"""
    symbol = symbol.upper()
    try:
        stock = yf.Ticker(symbol)
        info = stock.info
        # ดึงราคาจากหลายจุดเหมือนกันเพื่อกันพลาด
        price = info.get('currentPrice') or info.get('regularMarketPrice') or info.get('lastPrice')
        
        # ดึงค่าเงินบาท
        fx = yf.Ticker("USDTHB=X")
        thb_rate = fx.info.get('currentPrice') or fx.info.get('regularMarketPrice')

        if price and thb_rate:
            total_usd = price * amount
            total_thb = total_usd * thb_rate
            await ctx.send(f"💰 **{amount} {symbol}**\n= `${total_usd:,.2f}`\n= `฿{total_thb:,.2f}` (Rate: {thb_rate:.2f})")
        else:
            await ctx.send("❌ หาข้อมูลราคาไม่เจอครับ")
    except Exception as e:
        await ctx.send(f"❌ Error: {e}")

# ---------------------------------------------------------
# ⏰ TASKS & EVENTS
# ---------------------------------------------------------

@tasks.loop(hours=1)
async def auto_update():
    """ส่งราคาหุ้นอัตโนมัติทุก 1 ชม."""
    await bot.wait_until_ready()
    channel = bot.get_channel(STOCK_CHANNEL_ID)
    if channel:
        embed = await get_stock_data()
        if embed: 
            await channel.send(embed=embed)
            print(f"✅ Auto-update sent at {datetime.now()}")
    else:
        print(f"⚠️ Channel ID {STOCK_CHANNEL_ID} not found!")

@bot.event
async def on_ready():
    print(f'💰 Finance Bot Online: {bot.user}')
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="Stock Market 📉"))
    
    if not auto_update.is_running():
        auto_update.start()

@bot.command()
async def guide(ctx):
    """โพยอธิบายความหมายของแต่ละตัว (!guide)"""
    embed = discord.Embed(
        title="📚 Market Cheat Sheet",
        description="*Understanding symbols & indicators*",
        color=discord.Color.teal(), # สีเขียวน้ำทะเล ดูสบายตา
        timestamp=datetime.now()
    )

    # 1. Market ETFs (กองทุนดัชนี)
    embed.add_field(
        name="🌎 Market ETFs (The Benchmark)",
        value=(
            "**• SPY (S&P 500):** The top 500 US companies. Represents the **overall US economy**.\n"
            "**• QQQ (Nasdaq 100):** Top 100 non-financial tech companies. **High growth, high volatility**.\n"
            "**• TDEX (Thai SET50):** The top 50 companies in Thailand."
        ),
        inline=False
    )

    # 2. Market Health (สุขภาพตลาด - สำคัญมาก!)
    embed.add_field(
        name="🏥 Market Health Indicators (Watch Closely!)",
        value=(
            "**• US 10Y Bond (^TNX):** The 'Risk-Free Rate'.\n"
            "👉 *Rule:* If Yield **UP** 📈 = Tech Stocks **DOWN** 📉 (Investors sell risky stocks for safe bonds).\n\n"
            "**• VIX Index (^VIX):** The 'Fear Gauge'.\n"
            "👉 *Rule:* Below 20 = **Calm** 😎 | Above 30 = **Panic/Crash** 😱"
        ),
        inline=False
    )

    # 3. Commodities & Crypto
    embed.add_field(
        name="🏆 Commodities & Assets",
        value=(
            "**• Gold (GC=F):** Safe Haven. Moves up when people are scared or inflation is high.\n"
            "**• Crude Oil (CL=F):** Energy costs. High oil price = High inflation.\n"
            "**• Bitcoin (BTC):** 'Digital Gold'. Represents risk-on appetite."
        ),
        inline=False
    )
    
    embed.set_footer(text="Tip: Check ^TNX before buying Tech stocks!")
    await ctx.send(embed=embed)
    
# Run Bot
if TOKEN:
    bot.run(TOKEN)
else:
    print("❌ Error: ไม่พบ DISCORD_TOKEN")