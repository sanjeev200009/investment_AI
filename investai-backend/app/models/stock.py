from sqlalchemy import (BigInteger, Column, Date, DateTime, Float, Index,
                        Integer, String, Text, UniqueConstraint, func, text)

from app.database import Base


class MarketData(Base):
	"""Every scraped quote, one row per symbol per scrape.

	This is the append-only history. Read it when you want a series over time;
	read ``MarketDataLatest`` when you want the current price. All rows written by
	a single scrape share one ``recorded_at``, which is what makes a snapshot
	identifiable — the timestamp used to be taken per row inside the insert loop,
	so a single scrape landed under half a dozen distinct microsecond-apart
	timestamps and no query could group by "the snapshot".
	"""

	__tablename__ = "market_data"

	# (symbol, recorded_at DESC) rather than a plain index on symbol. Both serve a
	# symbol-only predicate -- symbol leads the composite -- but only the composite
	# also serves the ordering, which every per-symbol "most recent" or time-series
	# read needs. Two other indexes were dropped in e5f6a7b8c9d0: the standalone
	# symbol index this replaces, and a plain btree on market_id that duplicated
	# the primary key. Each cost a write on all ~6,000 inserts a day and served
	# nothing.
	__table_args__ = (
		Index("ix_market_data_symbol_recorded_at", "symbol", text("recorded_at DESC")),
	)

	market_id = Column(Integer, primary_key=True)
	symbol = Column(String(20), nullable=False)
	price = Column(Float, nullable=False)
	change = Column("change", Float)
	change_pct = Column(Float)
	volume = Column(Float)
	market_cap = Column(Float)
	recorded_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
	# The exchange's own ``lastTradedTime`` for this symbol. Added in a7b8c9d0e1f2
	# and nullable, because rows written before then genuinely do not have it and
	# no endpoint exists to backfill it from.
	#
	# This does *not* replace ``recorded_at``, and the distinction is the whole
	# reason both exist. ``recorded_at`` is one value for the entire scrape, which
	# is what makes a snapshot identifiable; ``last_traded_at`` is per symbol — a
	# live scrape returns 271 symbols with 271 distinct values — so it could never
	# serve that role. But ``recorded_at`` cannot say which *session* a quote
	# belongs to: cse.lk keeps serving the last session's numbers while the market
	# is shut, so a Thursday scrape of Tuesday's close is stamped Thursday. Only
	# this column knows it was Tuesday, and ``daily_close`` keys off it.
	last_traded_at = Column(DateTime(timezone=True))


class MarketDataLatest(Base):
	"""The current quote per symbol — exactly one row each.

	Every "what is X trading at" path used to derive this on the fly, and each
	did it differently and wrongly:

	*   ``stocks.py`` recomputed a ``GROUP BY symbol HAVING max(recorded_at)``
	    self-join on every request.
	*   ``dashboard.py`` ran one ``ORDER BY recorded_at DESC LIMIT 1`` per
	    holding — N+1.
	*   ``dashboard.py``'s watchlist ordered *all* history by volume and took six
	    rows, so once a second scrape existed the same symbol filled several
	    slots. With two snapshots the six-slot preview showed three symbols.
	*   ``ai_agent.py`` took ``ORDER BY recorded_at DESC LIMIT 10`` and called it
	    "top 10 movers" — arbitrary rows from the newest batch, not movers.

	Maintained by ``scrape_and_save_cse`` in the same transaction as the history
	insert, via ``ON CONFLICT (symbol) DO UPDATE``. A table rather than a
	materialised view: it updates transactionally with the write that makes it
	stale, with no refresh lock and no separate scheduling.

	A symbol that stops trading keeps its last known quote here rather than
	disappearing; ``recorded_at`` is how a caller judges staleness.
	"""

	__tablename__ = "market_data_latest"

	symbol = Column(String(20), primary_key=True)
	# The market_data row this was copied from. Deliberately not a foreign key:
	# the retention task added in I-06 prunes old history, and this table must not
	# constrain what history may be deleted. It exists so /stocks/market can keep
	# returning the market_id its response schema has always carried.
	market_id = Column(Integer)
	price = Column(Float, nullable=False)
	change = Column("change", Float)
	change_pct = Column(Float)
	volume = Column(Float)
	market_cap = Column(Float)
	# The scrape this quote came from — our clock, not the exchange's. The comment
	# here used to read "when the exchange reported this quote", which was wrong:
	# the trade summary carries no market-wide timestamp, so this is only ever when
	# we asked. ``last_traded_at`` below is the exchange's.
	recorded_at = Column(DateTime(timezone=True), nullable=False)
	# The exchange's ``lastTradedTime`` for this symbol. Nullable for the same
	# reason as on ``MarketData``: rows predating a7b8c9d0e1f2 have no value and
	# there is nothing to backfill from.
	last_traded_at = Column(DateTime(timezone=True))
	# When we last wrote this row. Differs from recorded_at when a scrape returns
	# an unchanged quote, so the two together distinguish "market is quiet" from
	# "the scraper has stopped running".
	updated_at = Column(DateTime(timezone=True), server_default=func.now(),
	                    onupdate=func.now(), nullable=False)


class MarketIndex(Base):
	"""Every scraped index reading, one row per index per exchange update.

	The append-only history behind index charts, mirroring ``MarketData``'s role
	for individual quotes. Covers all 22 indices cse.lk publishes: the two
	headline ones (ASPI, S&P SL20) and the 20 GICS industry-group indices.

	Two things differ from ``MarketData``, both because this feed carries the
	exchange's own timestamp and the trade summary does not:

	*   **``recorded_at`` is the exchange's ``transactionTime``, not the time we
	    scraped.** cse.lk keeps serving the last session's closing values while
	    the market is shut, so stamping these rows with ``now()`` would file
	    Tuesday's close under Thursday. ``updated_at`` on the latest table is
	    where our own clock goes.
	*   **``(index_code, recorded_at)`` is unique**, so re-scraping an unchanged
	    reading is a no-op instead of a duplicate row. The scrape task runs every
	    15 minutes; without this, a closed market would accumulate 22 identical
	    rows per run.

	That unique constraint's btree also serves every per-index time-series read
	(``WHERE index_code = ? ORDER BY recorded_at DESC``) by being scanned
	backwards, so unlike ``market_data`` this table needs no second index.
	"""

	__tablename__ = "market_index"

	__table_args__ = (
		UniqueConstraint("index_code", "recorded_at",
		                 name="uq_market_index_code_recorded_at"),
	)

	index_id = Column(Integer, primary_key=True)
	index_code = Column(String(20), nullable=False)
	value = Column(Float, nullable=False)
	change = Column("change", Float)
	change_pct = Column(Float)
	previous_close = Column(Float)
	# Today's activity in the index's constituents. NULL for ASPI and S&P SL20 --
	# cse.lk reports these per industry group only.
	turnover = Column(Float)
	volume = Column(Float)
	trades = Column(Integer)
	# When the exchange last recalculated this index, from its own feed.
	recorded_at = Column(DateTime(timezone=True), nullable=False)


class MarketIndexLatest(Base):
	"""The current reading per index — exactly one row each.

	Same pattern and same reasoning as ``MarketDataLatest``: a real table
	upserted in the scrape's own transaction, so no read path has to derive
	latest-per-index at request time.

	``name`` lives here and not on the history table. It is effectively static
	metadata ("Banks", "Energy"), so repeating it on every history row would cost
	storage for nothing and, worse, let one index accumulate two spellings if
	cse.lk ever renamed it. Charts join here for the label.
	"""

	__tablename__ = "market_index_latest"

	index_code = Column(String(20), primary_key=True)
	name = Column(String(120), nullable=False)
	value = Column(Float, nullable=False)
	change = Column("change", Float)
	change_pct = Column(Float)
	previous_close = Column(Float)
	turnover = Column(Float)
	volume = Column(Float)
	trades = Column(Integer)
	# When the exchange reported this reading.
	recorded_at = Column(DateTime(timezone=True), nullable=False)
	# When we last wrote this row. The pair distinguishes "the market is closed"
	# from "the scraper has stopped running" — while the market is shut,
	# recorded_at stays frozen at the last session's close and updated_at keeps
	# moving.
	updated_at = Column(DateTime(timezone=True), server_default=func.now(),
	                    onupdate=func.now(), nullable=False)


class DailyClose(Base):
	"""One row per symbol per trading day — the series behind every price chart.

	Replaces ``generateMockChartData()``, which built the stock detail chart from
	``Math.random()`` and labelled it with real times, and the dashboard's
	``current_value × [0.85, 0.82, 0.94, 1.0]`` four-point "performance" line.

	**``trade_date`` comes from the exchange's ``lastTradedTime``, never from our
	clock.** This is the load-bearing decision in the table and it is not
	theoretical. The two snapshots sitting in ``market_data`` when this was written
	were stamped 2026-07-05 and 2026-08-27 — a **Sunday**, when the CSE is shut,
	and a Thursday carrying the Tuesday 2026-08-25 session. Keying on the scrape
	date would have put a trading day on a weekend and duplicated one session
	across every day the market stayed closed, drawing a flat line over dates that
	never traded. That is the same class of fiction the mock generator produced,
	arrived at more respectably.

	**Upserted on every scrape, not written once by an end-of-day task.** The plan
	called for the latter; it is the wrong shape here. A single daily cron that
	misses its window — worker down, laptop shut — loses that day permanently,
	because cse.lk publishes no history endpoint to backfill from (``chartData``
	returns 400 for every parameter combination tried). Upserting every 15 minutes
	makes each scrape a checkpoint: ``high`` ratchets up, ``close`` tracks the last
	trade, and whatever the final scrape of the session saw stands as the close.

	The ``ON CONFLICT`` guard is ``last_traded_at <= excluded.last_traded_at``,
	matching ``MarketDataLatest`` — a retried or out-of-order task cannot walk a
	day's close backwards.

	Not backfilled from ``market_data``. Those rows never captured
	``lastTradedTime``, so their real session date is unknowable — the July
	snapshot could be Friday the 3rd or earlier — and they carry no open/high/low
	at all. A chart point at a guessed date is worse than a chart with fewer
	points, so the series starts from the first scrape that recorded the exchange's
	own timestamp.

	**``close`` is not guaranteed to lie within ``[low, high]``.** 19 of 271 symbols
	in the live sample reported a close outside their own day's range, and in every
	one of those cases ``closingPrice``, ``price`` and ``previousClose`` were the
	same number while ``open``/``high``/``low`` described real trades — INME traded
	1800–1875 across seven trades and reported a close of 1681. All 19 were thinly
	traded, so the feed's price field appears to lag for illiquid instruments. The
	value is stored as reported: clamping it would invent a price the exchange never
	printed, and dropping the row would discard an open, high and low that are not
	in doubt. ``close < low OR close > high`` finds them. This is why the price chart
	is drawn as a line of closes rather than candlesticks — a candle body outside its
	own wick is unreadable, whereas a line is merely, accurately, a little jagged.
	"""

	__tablename__ = "daily_close"

	# (symbol, trade_date) is the primary key, so its btree already serves the one
	# read this table has: WHERE symbol = ? ORDER BY trade_date. Ascending suits it
	# better than the DESC index on market_data — a chart wants oldest-first, and a
	# range query reads a contiguous forward span rather than seeking the newest
	# row. No second index.
	symbol = Column(String(20), primary_key=True)
	trade_date = Column(Date, primary_key=True)

	open = Column(Float)
	high = Column(Float)
	low = Column(Float)
	# NOT NULL because a row with no close is not a chart point. No CHECK
	# constraining it to [low, high]: the feed violates that for thinly traded
	# symbols (see the docstring), and a constraint would reject the whole scrape
	# over 19 rows rather than record what the exchange actually said.
	close = Column(Float, nullable=False)
	previous_close = Column(Float)

	volume = Column(Float)
	turnover = Column(Float)
	trades = Column(Integer)

	# The exchange's own timestamp for the last trade of this symbol on this day.
	# Both the source of ``trade_date`` and the ordering key for the upsert guard.
	last_traded_at = Column(DateTime(timezone=True), nullable=False)
	# Our clock. While the market is shut this keeps moving and last_traded_at does
	# not, which is how a caller tells a quiet market from a stopped scraper.
	updated_at = Column(DateTime(timezone=True), server_default=func.now(),
	                    onupdate=func.now(), nullable=False)


class CompanyInfo(Base):
	"""One row per symbol: what the company *is*, as opposed to what it traded at.

	Replaces four fabricated tiles on the stock detail screen. All four were
	modulus arithmetic on the live price — ``peRatio = 8 + (price % 15)``,
	``high52 = price × (1 + (price % 30) / 100)`` — presented as company
	fundamentals. Two stocks at the same price had identical "fundamentals", and a
	price crossing a multiple of 15 made the "P/E" jump. Sector filters on the home
	and browse screens were hardcoded ticker-prefix arrays for the same reason:
	nothing stored a sector.

	**Sourced from cse.lk's ``companyInfoSummery`` and ``companyProfile``**, two
	POSTs per symbol; all 291 symbols sweep in 7.8s at concurrency 6. Probed across
	every symbol in ``market_data_latest`` before this table was designed.

	**There is no P/E ratio and no EPS column, because there is no source.** 94
	distinct keys across both endpoints at every nesting depth contain no earnings,
	dividend, yield or net-asset figure. The tile was removed from the app instead
	of being given a column that is null for all 291 rows. What replaces it is real:
	market cap, a 12-month low the exchange itself computes, shares issued, sector,
	and beta against two indices.

	**Every column but ``name`` and ``refreshed_at`` is nullable, and the gaps are
	a class rather than noise.** ``CALI.U0000``, ``CALU.U0000`` and ``CALC.U0000``
	— unit trusts — have no sector, no beta and no market cap; ``AMF.N0000``, a
	fund, has no market cap or 12-month range either. A closed-end fund has no
	industry sector, so null is the correct answer and the API returns it rather
	than a substitute.

	**``week52_high``/``week52_low`` come from cse.lk, not from ``DailyClose``.**
	The remediation plan proposed deriving them from I-06's daily series, which is
	sound and needs no new source — but that series starts accumulating at its
	first scrape, so a real 52-week range from it is 52 weeks away. The exchange
	publishes ``p12HiPrice``/``p12LowPrice`` today. Worth noting the two will
	disagree slightly once ``DailyClose`` is deep enough to compare: cse.lk's range
	is over all trades, ours would be over daily closes only.

	**``week52_high`` is stored but deliberately not served, and ``week52_low`` is.**
	Measured over all 287 symbols with a range: 26 report a 12-month span of 5x or
	more and 13 of 10x or more — MERC 22.0–10,999.0 while trading at 22.7, CPRT
	29.8–4,700.0 at 30.8. Those are pre-split nominal highs the exchange never
	restated, and on a "52W HIGH" tile they say the stock is down 99.8% on the year.
	The one candidate suppression rule (``p12HiPrice == allHiPrice``) catches 16 of
	24 suspects and false-positives on 2 of 15 controls — MELS and AEL, which are
	legitimately at all-time highs — so there is no reliable discriminator.
	``week52_low`` has **zero** contaminated values, and the asymmetry is structural:
	a forward split inflates old nominal highs and can never inflate a low. So the
	low is served, the high is not, and the app's 52-week high grows out of I-06's
	``daily_close``, which is split-consistent by construction.
	"""

	__tablename__ = "company_info"

	# The full symbol with its class suffix, so this joins market_data_latest and
	# daily_close directly. cse.lk also returns a bare "JKH", deliberately unused
	# as the key — it is not unique across a company's share classes.
	symbol = Column(String(20), primary_key=True)

	# NOT NULL: a row that cannot be labelled identifies nothing. This is also the
	# column that fixes the browse screen, which read `s.name` off a payload that
	# never had it, so every row rendered nameless and name search matched nothing.
	name = Column(String(200), nullable=False)

	# The sector string exactly as cse.lk filed it. Not a category — 288 populated
	# values are **39 distinct strings** for 20 industry groups: "Food Beverage &
	# Tobacco" (34), "FOOD BEVERAGE & TOBACCO" (10) and "Food, Beverage & Tobacco"
	# (2) are one sector typed three ways, and "Materials (1510)", "- Property &
	# Casualty Insurance" and "Banks Finance & Insurance" are a GICS code, a
	# sub-industry and a pre-2019 CSE sector name respectively.
	#
	# Kept verbatim anyway, because it is the raw evidence: when the normalisation
	# below gets something wrong, this column is what proves it and what a corrected
	# mapping is re-derived from. Nothing filters on it.
	sector = Column(String(80))

	# ``sector`` folded onto one of the exchange's own 20 industry-group index names
	# by ``app.services.sectors.canonical_sector``, so a sector filter and that
	# sector's index reading share one vocabulary. This is the column the API groups
	# and filters by.
	#
	# Null in two cases that mean the same thing to a client and must not be
	# conflated in the mapping: no sector in the feed at all (3 unit trusts), or a
	# sector string no source resolves to one group (3 symbols — "Industrials" is a
	# GICS *sector* spanning three groups, "Trading" belongs to a seafood processor).
	# Both are "unknown group", so both are left out of the chip list rather than
	# swept into an "Other" bucket that would read as a real sector.
	sector_group = Column(String(80))

	market_cap = Column(Float)
	# Percent of total market capitalisation, as reported (4.55 for JKH).
	market_cap_pct = Column(Float)

	# BigInteger, not Integer: JKH has 17,740,212,930 shares issued, three orders
	# of magnitude past int32.
	shares_issued = Column(BigInteger)
	par_value = Column(Float)
	isin = Column(String(20))

	week52_high = Column(Float)
	week52_low = Column(Float)
	# **Not split-adjusted.** JKH's all_time_high is 430.25 against a close of 19.80
	# and a 12-month range of 17.80–23.90: a pre-split price the exchange has never
	# restated. Stored because it is what cse.lk publishes and dropping a column to
	# hide a caveat is worse than documenting it, but nothing in the app renders it
	# beside the current price, where it would read as a 95% collapse.
	all_time_high = Column(Float)
	all_time_low = Column(Float)

	# Beta against the Total Return ASI and against S&P SL20. Kept because this app
	# assigns users a risk profile, and beta is the one published figure that says
	# how much a holding amplifies market movement.
	beta_asi = Column(Float)
	beta_sl20 = Column(Float)
	# The period the beta covers, so a displayed value can say how old it is rather
	# than implying it is live.
	beta_period = Column(String(20))

	board = Column(String(40))
	established = Column(String(20))
	website = Column(String(300))
	# Text, not String: these run to several hundred words, and truncating a
	# description mid-sentence to fit a column is silent corruption that only
	# surfaces in the UI.
	business_summary = Column(Text)

	# Our clock — cse.lk publishes no timestamp for company data. Doubles as the
	# no-backwards guard for the upsert and as the basis of any staleness claim.
	refreshed_at = Column(DateTime(timezone=True), nullable=False)

	__table_args__ = (
		# A filter, not a lookup key: "every stock in Banking" scans this. On
		# sector_group, not sector — the raw string is never filtered on, so
		# indexing it would cost writes to serve no query. Partial on NOT NULL
		# because the six symbols with no resolvable group are never a filter
		# target and their index entries would only be scanned past.
		Index("ix_company_info_sector_group", "sector_group",
		      postgresql_where=text("sector_group IS NOT NULL")),
	)


class NewsSentiment(Base):
	"""One row per (article, company mentioned). Written by app.services.news.

	**One article can be several rows, and that is the point.** A story naming
	three listed companies becomes three rows sharing a url, so ``symbol`` stays a
	plain indexed equality filter and "sentiment for SAMP.N0000" is one index
	scan. ``uq_news_url_symbol`` is what keeps that from degenerating into
	duplicates across the 48 scrape runs a day.

	Articles that name no listed company are stored once under ``GENERAL`` — a
	rupee fixing or a T-bill auction genuinely is market-wide. That is different
	from "attribution failed", and the difference matters: before I-08, *every*
	row was ``GENERAL`` because the writer never looked at the article's content
	at all, so the label carried no information.
	"""

	__tablename__ = "news_sentiment"

	news_id = Column(Integer, primary_key=True, index=True)
	symbol = Column(String(20), nullable=False, index=True)
	headline = Column(String(500), nullable=False)
	# 500, narrowed from 1000 in c9d0e1f2a3b4: this is half of a unique composite
	# index and a btree key has to stay inside Postgres' ~2704-byte limit. Longest
	# URL observed across the two live sources is 151 characters.
	url = Column(String(500), nullable=False)
	# The publication's name ("Daily FT", "EconomyNext"), not the index URL the
	# story was found on. The URL is already in `url`, and a screen showing
	# provenance wants something a reader recognises.
	source = Column(String(120))
	# Short display string: the LLM's summary once analyse_sentiment_batch has run,
	# the article's opening 500 characters until then. A real lede either way, so
	# the row is useful before the LLM reaches it and still useful if it never does.
	summary = Column(Text)
	# The full article text, which is what summarise_article() and VADER read.
	# Stored rather than re-derived because the summariser is a separate Celery
	# task from the scrape: without this column it would have to re-fetch every
	# article page, doubling requests to two publishers for text already read.
	body = Column(Text)
	sentiment_score = Column(Float)
	sentiment_label = Column(String(20))
	# Parsed per source — economynext publishes article:published_time, ft.lk
	# publishes no date metadata at all and only renders it in span.gtime. Both
	# date in Asia/Colombo local time with no offset, so the parser converts before
	# storing; a naive read would place every article 5.5 hours early.
	published_at = Column(DateTime(timezone=True))
	scraped_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

	__table_args__ = (
		# One row per article per company. Enforced in the database, not in the
		# ingest code, because the scrape beat runs every 30 minutes over index
		# pages that serve the same stories for hours — a dedupe bug here compounds
		# 48 times a day. The table previously had no unique constraint of any
		# kind.
		Index("uq_news_url_symbol", "url", "symbol", unique=True),
	)


class PricePrediction(Base):
	__tablename__ = "price_predictions"

	prediction_id = Column(Integer, primary_key=True, index=True)
	symbol = Column(String(20), nullable=False, index=True)
	predicted_price = Column(Float, nullable=False)
	model_version = Column(String(50), nullable=False)
	generated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
