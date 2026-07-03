# Riffle: The Fly Guide MVP Brief

## Product Wedge

Riffle helps experienced fly anglers decide where to fish today among rivers and sections they already know.

The MVP should not try to be a full fishing map, access platform, social network, or catch log. Its first job is to answer:

> Which of my usual waters are worth fishing today, and why?

## MVP Region

Start with Idaho, but model the product around reaches rather than broad rivers.

Example:

- Boise River - In Town
- Boise River - South Fork
- Boise River - Middle Fork
- Henry's Fork - Box Canyon
- Henry's Fork - Harriman Ranch
- Snake River - South Fork Canyon
- Big Wood - Ketchum
- Silver Creek - Preserve
- Teton River - Driggs/Victor
- Salmon River - Upper Stanley
- Clearwater - Middle Fork
- St. Joe - Upper

This structure matters because forks, tailwaters, spring creeks, canyon sections, and in-town water behave differently even when anglers casually refer to them by the same parent river.

## Core User

The first user is not a tourist asking "Where can I fish?"

The first user is a frequent Idaho fly angler asking:

- Should I fish before work?
- Should I drive two hours or stay local?
- Is my favorite reach blown out?
- Is the water too warm?
- Is it a float day, wade day, or skip day?
- Did anything change since yesterday?

## MVP Screens

### 1. Daily Idaho Dashboard

Purpose: fast morning scan.

Must show:

- Best bets today
- Fishable with caveats
- Skip or wait
- Limited/insufficient confidence
- Reach cards with status, CFS, water temp, weather window, likely hatch, and report freshness

### 2. Reach Detail

Purpose: explain the recommendation.

Must show:

- Daily status: Best, Watch, Skip, or Limited
- Plain-English reason
- Flow and 24-hour trend
- 7-day flow trend
- Water temperature if available
- Weather window
- Barometric pressure trend
- Wind and storm risk
- Likely hatches
- Local report links with source/date attribution
- Data confidence

This page should also act as the standing river profile for that reach, not only a daily conditions panel.

Profile content:

- Two or more river photos or image slots
- Overview of how the reach fishes
- Water character
- Best fishing style: wade, float, technical dry-fly, quick local session, backcountry, etc.
- Common seasonal hatches
- Main risks: runoff, dam releases, wind, warm water, poor clarity, access/road conditions
- Source links and local report attribution

### 3. Daily Digest

Purpose: repeat traffic.

This can be email, RSS, or a static daily page.

The digest should include:

- Top 3 Idaho bets
- Biggest improvements since yesterday
- Biggest declines since yesterday
- Heat/warm-water warnings
- Runoff watchlist
- Freshest local reports

## Recommendation Categories

### Best

The reach has favorable conditions and enough data confidence to recommend.

Common signals:

- Stable or improving flow
- Water temp in a productive range
- No major storm/wind problem during the likely fishing window
- Seasonal hatch alignment
- Fresh report or strong data confidence

### Watch

The reach is fishable, but timing or style matters.

Common signals:

- High but falling flow
- Good early window before wind/heat
- Technical dry-fly conditions
- Good float conditions but poor wade conditions
- Slight storm or clarity risk

### Skip

The reach is a bad bet today.

Common signals:

- Rising runoff
- Unsafe/high flow
- Too warm for ethical trout fishing
- Heavy wind or storm risk
- Poor clarity
- Better nearby options

### Limited

The system does not know enough.

Common signals:

- No recent report
- Missing water temp
- Uncertain clarity
- Sparse gage coverage
- Conflicting indicators

Limited is important because it builds trust. The app should admit uncertainty.

## Scoring Model

Use a transparent rules-based score first. Avoid opaque AI scoring in the MVP.

Suggested score components:

- Flow fit: 0-25
- Flow trend: 0-15
- Water temperature: 0-20
- Weather window: 0-15
- Pressure/wind/storm risk: 0-10
- Hatch likelihood: 0-10
- Report freshness/confidence: 0-5

Then map score plus hard-stop rules to a recommendation.

Hard-stop examples:

- Water too warm: Skip or warning
- Rapidly rising runoff: Skip
- Severe thunderstorm/high wind alert: Watch or Skip
- Missing key data: Limited unless local report confirms

## Data Sources

### USGS

Use for:

- Streamflow/CFS
- Gage height
- Water temperature where available
- Historical daily values
- Trend detection

Important implementation note:

The older USGS Water Services endpoints are useful for prototyping, but the long-term implementation should account for USGS transition toward the newer water data API.

### National Weather Service

Use for:

- Point forecast
- Hourly forecast
- Wind
- Temperature
- Precipitation/storm risk
- Weather alerts
- Nearby observations

NWS requires a clear User-Agent string. Build that into the backend from day one.

### Local Fly Shops and Guides

Use for:

- Report freshness
- Clarity comments
- Hatch observations
- Access/road notes
- Human confirmation of what the raw data implies

Preferred approach:

- Link and attribute clearly.
- Store source URL, title, date, and short excerpt only when allowed.
- Summarize cautiously.
- Eventually invite shops to submit reports directly.

Avoid copying full reports.

## Backend MVP Shape

The app itself should not scrape/fetch everything every time a user loads the page. Use a separate scheduled data job.

Why:

- Faster pages
- Lower API pressure
- Easier retry/error handling
- Better SEO because pages can be generated with stable daily data
- Clear separation between "collect conditions" and "display conditions"

Daily job:

1. Load reach catalog.
2. Fetch USGS values for mapped gages.
3. Fetch NWS forecast/observations for mapped points.
4. Fetch or ingest report metadata.
5. Calculate status and confidence.
6. Generate a daily conditions object.
7. Render dashboard, reach pages, and digest.

Recommended schedule:

- Run once before the morning fishing window, around 5:00-6:00 AM Mountain Time.
- Optionally run a lighter refresh around noon for wind, storms, heat, and water-temperature warnings.
- Store each run as a dated conditions snapshot so the app can show "better/worse than yesterday."

First automation output:

- `daily_conditions_YYYY-MM-DD.json`
- one record per reach
- raw source values
- normalized metrics
- recommendation status
- confidence score
- plain-English reason
- source attribution

Suggested first stack:

- Static frontend or Next.js
- Small scheduled backend job
- SQLite or Postgres
- JSON reach catalog
- Daily generated pages for SEO

## SEO Strategy

Traffic should come from useful daily and evergreen pages.

Target page patterns:

- `/idaho`
- `/idaho/boise-river/in-town`
- `/idaho/boise-river/south-fork`
- `/idaho/henrys-fork/box-canyon`
- `/idaho/silver-creek/preserve`

Good page titles:

- Boise River In Town Fishing Conditions Today
- South Fork Boise River Flows and Fishing Outlook
- Henry's Fork Box Canyon Fishing Conditions
- Idaho Fly Fishing Conditions Today

The site should publish stable pages that update daily, not just a single dynamic app screen.

## What Not To Build First

- Native mobile app
- User catch logging
- Social feed
- Secret spot discovery
- Complex access/private land mapping
- Paid subscriptions
- AI chat as the primary interface

Those can come later. The first product should be a trusted morning read.

## Next Implementation Step

Turn the static prototype into a small app with:

- `reaches.json`
- generated dashboard
- generated reach detail pages
- mock daily condition data
- scoring function
- source attribution model

Once that works, wire live USGS/NWS data for 2-3 reaches before expanding the catalog.
