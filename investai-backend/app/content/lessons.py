"""Beginner lessons for the Learn tab and the assistant's knowledge search.

DRAFT CONTENT for the project team and supervisor to review before release.
Written for first-time investors on the Colombo Stock Exchange; plain language,
one idea per lesson. Figures in examples are illustrative arithmetic, not market
data, and say so. Facts about the CSE are kept general where the exact rule can
change (fees, settlement periods); check them against cse.lk and the SEC
Sri Lanka before relying on them.

`theme` maps each lesson to a broad OECD/INFE financial-literacy area (knowledge
of risk and return, diversification, product understanding, fraud awareness).
Confirm the framework version the dissertation cites before quoting the mapping.

The same text is what the AI assistant retrieves (RAG) when a user asks a
concept question, so the app and the assistant teach the same thing.
"""

from __future__ import annotations

LESSONS: list[dict] = [
    {
        "id": "what-is-a-share",
        "title": "What is a share?",
        "theme": "Product understanding",
        "minutes": 3,
        "summary": "A share is a small piece of ownership in a company, and it can rise or fall in value.",
        "sections": [
            ("Owning part of a company",
             "When a company lists on the stock exchange, it divides its ownership into many equal "
             "parts called shares. Buying one share makes you a part-owner, called a shareholder. "
             "If the company has 1,000,000 shares and you own 100, you own one ten-thousandth of it."),
            ("How shareholders can earn",
             "There are two ways. Capital gain: you sell a share for more than you paid. Dividend: the "
             "company shares part of its profit with shareholders, usually as cash per share. Many "
             "companies pay dividends only in some years, and some never do."),
            ("How shareholders can lose",
             "Share prices move every trading day. If the company does badly, or investors expect it "
             "to, the price can fall below what you paid, and you can lose part of your money. A "
             "share has no guaranteed value."),
        ],
        "key_terms": ["share", "shareholder", "dividend", "capital gain"],
    },
    {
        "id": "how-the-cse-works",
        "title": "How the Colombo Stock Exchange works",
        "theme": "Product understanding",
        "minutes": 4,
        "summary": "The CSE is Sri Lanka's stock market; you trade through a licensed stockbroker and a CDS account.",
        "sections": [
            ("The exchange",
             "The Colombo Stock Exchange (CSE) is where shares of Sri Lankan listed companies are bought "
             "and sold. Around 290 companies are listed, grouped into 20 industry sectors such as Banks, "
             "Capital Goods and Telecommunication Services. It is regulated by the Securities and "
             "Exchange Commission of Sri Lanka (SEC)."),
            ("How you trade",
             "Individuals do not trade on the exchange directly. You open an account with a licensed "
             "stockbroker, who also opens a Central Depository System (CDS) account in your name. Your "
             "shares are held electronically in that CDS account. You place orders through the broker, "
             "often in their app."),
            ("When trading happens",
             "Regular trading runs on weekdays, excluding market holidays, from 9:30 am to 2:30 pm Sri "
             "Lanka time. Outside those hours prices do not change; the prices you see are from the "
             "last session, which is why InvestAI always shows the date of a price."),
            ("Costs",
             "Every purchase and sale carries brokerage and other fees, charged as a percentage of the "
             "trade value. Ask your broker for the current rates: fees matter more on small, frequent "
             "trades."),
        ],
        "key_terms": ["CSE", "stockbroker", "CDS account", "trading hours", "SEC Sri Lanka"],
    },
    {
        "id": "market-indices",
        "title": "Reading market indices: ASPI and S&P SL20",
        "theme": "Product understanding",
        "minutes": 3,
        "summary": "An index is one number that summarises how a group of shares moved.",
        "sections": [
            ("What an index is",
             "Following 290 prices at once is hard, so the market summarises them in indices. An index "
             "rises when most of its shares, weighted by size, rise, and falls when they fall."),
            ("ASPI",
             "The All Share Price Index covers every listed company, weighted by market value, so large "
             "companies move it more than small ones. When people say 'the market was up today', they "
             "usually mean the ASPI."),
            ("S&P SL20",
             "The S&P SL20 follows 20 of the largest and most actively traded companies. It shows how "
             "the big, established names are doing, which can differ from the whole market."),
            ("Sector indices",
             "Each of the 20 industry groups has its own index, for example Banks. Comparing a sector "
             "index with the ASPI shows whether that sector did better or worse than the market."),
        ],
        "key_terms": ["index", "ASPI", "S&P SL20", "sector index", "market value weighting"],
    },
    {
        "id": "price-volume-liquidity",
        "title": "Price, volume and liquidity",
        "theme": "Product understanding",
        "minutes": 3,
        "summary": "How often a share trades matters as much as its price.",
        "sections": [
            ("Volume and turnover",
             "Volume is how many shares changed hands in a session. Turnover is the total money traded: "
             "volume multiplied by price. High turnover means many buyers and sellers are active."),
            ("Liquidity",
             "A liquid share trades often, so you can usually buy or sell quickly at close to the last "
             "price. An illiquid share may go days without a trade; selling it can take time, or mean "
             "accepting a lower price."),
            ("Why beginners should care",
             "Large percentage moves in rarely traded shares can come from a single small trade, not "
             "from real news. A +15% day on very low volume is weak evidence of anything. InvestAI's "
             "stock scores include liquidity for this reason."),
        ],
        "key_terms": ["volume", "turnover", "liquidity", "illiquid"],
    },
    {
        "id": "risk-and-return",
        "title": "Risk and return",
        "theme": "Knowledge of risk and return",
        "minutes": 4,
        "summary": "Higher possible returns come with higher chances of loss.",
        "sections": [
            ("The trade-off",
             "Safer savings, such as a bank fixed deposit, pay a known return. Shares may earn more over "
             "time, but their value goes up and down and can stay down for a long time. That uncertainty "
             "is the risk you accept for a chance of a higher return."),
            ("Volatility",
             "Volatility is how much a price moves around. A volatile share can rise or fall sharply in "
             "days. Volatility is not the same as losing money, but it makes losses more likely if you "
             "need to sell at a bad moment."),
            ("Time horizon",
             "Money you need soon, such as next year's fees, is poorly suited to shares because you may "
             "have to sell during a fall. Money you will not need for several years can ride out "
             "short-term swings."),
            ("A rule to keep",
             "Only invest money you can afford to leave invested and could afford to lose part of. "
             "Your InvestAI risk profile reflects how you answered these questions."),
        ],
        "key_terms": ["risk", "return", "volatility", "time horizon", "fixed deposit"],
    },
    {
        "id": "diversification",
        "title": "Diversification",
        "theme": "Diversification",
        "minutes": 3,
        "summary": "Spreading money across companies and sectors reduces the damage any one can do.",
        "sections": [
            ("Do not rely on one company",
             "If all your money is in one company and it runs into trouble, your whole investment "
             "suffers. Holding several companies means one bad result hurts less."),
            ("Across sectors too",
             "Companies in the same sector often move together; for example, several banks can fall "
             "on the same interest-rate news. Holding shares in different sectors spreads that risk. "
             "The Portfolio tab shows your allocation by sector."),
            ("What it cannot do",
             "Diversification reduces the risk from any single company, but not the risk of the whole "
             "market falling. It is a way to manage risk, not remove it."),
        ],
        "key_terms": ["diversification", "sector", "allocation", "concentration"],
    },
    {
        "id": "fundamentals-basics",
        "title": "Company basics: EPS, P/E, dividend yield, market cap",
        "theme": "Product understanding",
        "minutes": 5,
        "summary": "Four common numbers for comparing companies, and what each leaves out.",
        "sections": [
            ("Earnings per share (EPS)",
             "A company's profit for the year divided by its number of shares. Example (illustrative): "
             "profit of Rs. 1,000 million and 100 million shares gives an EPS of Rs. 10."),
            ("Price-to-earnings ratio (P/E)",
             "Share price divided by EPS. With a price of Rs. 150 and an EPS of Rs. 10, the P/E is 15: "
             "investors are paying 15 times one year's earnings. A high P/E can mean investors expect "
             "growth, or that the share is expensive. Compare P/E only between similar companies."),
            ("Dividend yield",
             "Yearly dividend per share divided by share price. A Rs. 6 dividend on a Rs. 150 share is "
             "a 4% yield. Past dividends do not promise future ones."),
            ("Market capitalisation",
             "Share price multiplied by the number of shares: the market's total value for the company. "
             "It tells you size, not quality."),
            ("The limit of ratios",
             "Each number describes the past or one moment. None of them tells you on its own whether "
             "to buy. Use them to ask better questions."),
        ],
        "key_terms": ["EPS", "P/E ratio", "dividend yield", "market capitalisation"],
    },
    {
        "id": "news-and-hype",
        "title": "Reading news without getting caught by hype",
        "theme": "Fraud awareness",
        "minutes": 3,
        "summary": "Check the source, check the volume, and be wary of anyone promising quick gains.",
        "sections": [
            ("Official sources first",
             "Listed companies publish results and material announcements through the CSE. Those are "
             "the primary source; newspaper and social-media stories are second-hand."),
            ("Hype and pump-and-dump",
             "A pump-and-dump is when people buy a thinly traded share, spread excited messages to "
             "attract buyers, then sell to them at the higher price. Warning signs: pressure to act "
             "today, promised returns, tips from strangers, and big moves in rarely traded shares."),
            ("News tone is not a forecast",
             "InvestAI labels news as positive, neutral or negative in tone. Positive news can already "
             "be reflected in the price, and tone scoring can misread a story. Treat it as context."),
            ("Report concerns",
             "Suspected market manipulation or unlicensed investment schemes can be reported to the "
             "SEC Sri Lanka."),
        ],
        "key_terms": ["announcement", "pump and dump", "sentiment", "market manipulation"],
    },
    {
        "id": "using-investai",
        "title": "How InvestAI helps, and its limits",
        "theme": "Consumer protection",
        "minutes": 3,
        "summary": "InvestAI explains the market; it does not tell you what to buy.",
        "sections": [
            ("Where the numbers come from",
             "Prices, indices and company details are collected from the CSE's public website. News "
             "comes from Daily FT and EconomyNext. Every price shows the date of its trading session."),
            ("How stock scores work",
             "'Stocks to study' ranks shares with a transparent score from four measured factors: "
             "today's move, the trend over about four weeks, trading activity and news tone. Tap a "
             "stock to see each factor's weight and contribution. Your risk profile changes the "
             "weights. A high score means worth studying, not worth buying."),
            ("What the assistant will not do",
             "It will not tell you to buy, sell or hold a share, promise a price, or place trades. It "
             "can be wrong, so check important facts with your broker and the CSE."),
        ],
        "key_terms": ["InvestAI", "score", "educational", "not financial advice"],
    },
]

LESSONS_BY_ID: dict[str, dict] = {lesson["id"]: lesson for lesson in LESSONS}


def lesson_text(lesson: dict) -> str:
    """The whole lesson as one passage, for embedding and for the assistant."""
    body = " ".join(f"{h}. {t}" for h, t in lesson["sections"])
    return f"{lesson['title']}. {lesson['summary']} {body}"


def keyword_rank(query: str, limit: int = 2) -> list[dict]:
    """Fallback ranking when embeddings are unavailable: shared words, with
    title and key-term hits counting extra. Deterministic and offline."""
    words = {w for w in query.lower().replace("?", " ").replace(",", " ").split() if len(w) > 2}
    if not words:
        return []
    scored = []
    for lesson in LESSONS:
        text = lesson_text(lesson).lower()
        strong = f"{lesson['title']} {' '.join(lesson['key_terms'])}".lower()
        score = sum(text.count(w) for w in words) + 3 * sum(w in strong for w in words)
        if score:
            scored.append((score, lesson))
    scored.sort(key=lambda s: s[0], reverse=True)
    return [lesson for _, lesson in scored[:limit]]
