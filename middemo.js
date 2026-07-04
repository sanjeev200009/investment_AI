const pptxgen = require("pptxgenjs");

// ─────────────────────────────────────────────────────────────────────────
// PALETTE — pulled from InvestAI's own in-app brand colors
// ─────────────────────────────────────────────────────────────────────────
const C = {
    navy: "002743",       // dominant / primary
    navyDeep: "001A2E",   // darker navy for gradknown bg
    navyLight: "1C3D5A",  // secondary container
    ice: "F4F8FC",        // light background tint
    iceBlue: "CFE5FF",    // light accent
    iceBlueMid: "89A8CA", // mid accent (on primary container)
    teal: "0EA5A5",       // accent - progress / success
    tealLight: "2DD4BF",
    gold: "E8A93A",       // accent - in progress / highlight
    goldLight: "F6D896",
    red: "C0392B",
    white: "FFFFFF",
    ink: "0F1D2B",         // main text
    slate: "51677D",       // muted text
    slateLight: "8CA0B3",
    cardLine: "E3EBF2",
};

const ICON = (name, color) => `/home/claude/investai_deck/icons/${name}_${color}.png`;

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE"; // 13.333 x 7.5
pres.author = "Sanjeev & Sajeevan";
pres.title = "InvestAI — Mid Demonstration Phase 2";

const PW = 13.333, PH = 7.5;

// ─────────────────────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────────────────────
function freshShadow(opacity = 0.12, blur = 14, offset = 3, angle = 90) {
    return { type: "outer", color: "0B1E33", blur, offset, angle, opacity };
}

function addFooter(slide, pageNum, label) {
    slide.addText(label || "InvestAI  |  Mid-Demonstration Phase 2", {
        x: 0.5, y: PH - 0.42, w: 8, h: 0.3, fontSize: 9, color: C.slateLight,
        fontFace: "Calibri", align: "left", margin: 0,
    });
    slide.addText(String(pageNum), {
        x: PW - 1.0, y: PH - 0.42, w: 0.5, h: 0.3, fontSize: 9, color: C.slateLight,
        fontFace: "Calibri", align: "right", margin: 0,
    });
}

function sectionTag(slide, text, x = 0.6, y = 0.42) {
    slide.addShape(pres.shapes.ROUNDED_RECTANGLE, {
        x, y, w: 2.6, h: 0.38, rectRadius: 0.19,
        fill: { color: C.iceBlue }, line: { type: "none" },
    });
    slide.addText(text.toUpperCase(), {
        x, y, w: 2.6, h: 0.38, fontSize: 11, bold: true, color: C.navy,
        align: "center", valign: "middle", fontFace: "Calibri", charSpacing: 1, margin: 0,
    });
}

function titleBlock(slide, title, subtitle, y = 0.9) {
    slide.addText(title, {
        x: 0.6, y, w: PW - 1.2, h: 0.75, fontSize: 32, bold: true, color: C.navy,
        fontFace: "Cambria", align: "left", margin: 0,
    });
    if (subtitle) {
        slide.addText(subtitle, {
            x: 0.6, y: y + 0.72, w: PW - 1.2, h: 0.4, fontSize: 14, color: C.slate,
            fontFace: "Calibri", align: "left", margin: 0,
        });
    }
}

// Rounded progress bar with label; status: 'done' | 'progress' | 'planned'
function progressBar(slide, x, y, w, pct, colorFill, trackColor = "E4ECF3") {
    const h = 0.22;
    slide.addShape(pres.shapes.ROUNDED_RECTANGLE, {
        x, y, w, h, rectRadius: 0.11, fill: { color: trackColor }, line: { type: "none" },
    });
    const fillW = Math.max(w * (pct / 100), h); // keep pill shape at low pct
    slide.addShape(pres.shapes.ROUNDED_RECTANGLE, {
        x, y, w: fillW, h, rectRadius: 0.11, fill: { color: colorFill }, line: { type: "none" },
    });
}

// Screenshot placeholder card
function uiPlaceholder(slide, x, y, w, h, label) {
    slide.addShape(pres.shapes.ROUNDED_RECTANGLE, {
        x, y, w, h, rectRadius: 0.12,
        fill: { color: C.ice }, line: { color: C.iceBlueMid, width: 1.25, dashType: "dash" },
    });
    slide.addImage({ path: ICON("mobile", "89A8CA"), x: x + w / 2 - 0.28, y: y + h / 2 - 0.55, w: 0.56, h: 0.56 });
    slide.addText("UPLOAD UI SCREENSHOT", {
        x: x + 0.15, y: y + h / 2 - 0.02, w: w - 0.3, h: 0.28, fontSize: 9.5, bold: true,
        color: C.iceBlueMid, align: "center", fontFace: "Calibri", charSpacing: 1, margin: 0,
    });
    slide.addText(label, {
        x: x + 0.15, y: y + h - 0.42, w: w - 0.3, h: 0.32, fontSize: 11.5, bold: true,
        color: C.navy, align: "center", fontFace: "Calibri", margin: 0,
    });
}

// Objective status chip
function statusChip(slide, x, y, text, color) {
    const w = 1.55, h = 0.32;
    slide.addShape(pres.shapes.ROUNDED_RECTANGLE, {
        x, y, w, h, rectRadius: 0.16, fill: { color }, line: { type: "none" },
    });
    slide.addText(text, {
        x, y, w, h, fontSize: 10, bold: true, color: C.white, align: "center", valign: "middle",
        fontFace: "Calibri", margin: 0,
    });
}

// ═══════════════════════════════════════════════════════════════════════
// SLIDE 1 — TITLE
// ═══════════════════════════════════════════════════════════════════════
{
    const s = pres.addSlide();
    s.background = { color: C.navyDeep };

    // Soft glow shapes for depth
    s.addShape(pres.shapes.OVAL, { x: 9.3, y: -2.2, w: 7, h: 7, fill: { color: C.navyLight, transparency: 55 }, line: { type: "none" } });
    s.addShape(pres.shapes.OVAL, { x: -2.5, y: 4.6, w: 6, h: 6, fill: { color: C.navyLight, transparency: 65 }, line: { type: "none" } });

    s.addShape(pres.shapes.ROUNDED_RECTANGLE, {
        x: 0.6, y: 0.7, w: 2.65, h: 0.42, rectRadius: 0.21,
        fill: { color: C.tealLight, transparency: 82 }, line: { color: C.tealLight, width: 1 },
    });
    s.addText("MID-DEMONSTRATION · PHASE 2", {
        x: 0.6, y: 0.7, w: 2.65, h: 0.42, fontSize: 10.5, bold: true, color: C.tealLight,
        align: "center", valign: "middle", fontFace: "Calibri", charSpacing: 1, margin: 0,
    });

    s.addImage({ path: ICON("robot", "FFFFFF"), x: 0.62, y: 2.55, w: 0.85, h: 0.85 });
    s.addText("InvestAI", {
        x: 1.62, y: 2.35, w: 8, h: 1.15, fontSize: 56, bold: true, color: C.white,
        fontFace: "Cambria", align: "left", margin: 0,
    });
    s.addText("An AI-Powered Investment Assistant for Beginner Investors\nin the Colombo Stock Exchange (CSE)", {
        x: 0.65, y: 3.55, w: 10.5, h: 0.9, fontSize: 17, color: C.iceBlue,
        fontFace: "Calibri", align: "left", margin: 0, lineSpacingMultiple: 1.25,
    });

    // divider
    s.addShape(pres.shapes.LINE, { x: 0.65, y: 4.75, w: 5.2, h: 0, line: { color: C.navyLight, width: 1.5 } });

    s.addText([
        { text: "Team Members\n", options: { bold: true, color: C.slateLight, fontSize: 11, breakLine: true } },
        { text: "S. Sanjeev  —  Backend & Database Engineering\n", options: { color: C.white, fontSize: 14, breakLine: true } },
        { text: "P. Sajeevan  —  Frontend & UI Integration", options: { color: C.white, fontSize: 14 } },
    ], { x: 0.65, y: 4.95, w: 8, h: 1.1, fontFace: "Calibri", align: "left", margin: 0, lineSpacingMultiple: 1.3 });

    s.addText("BSc (Hons) in Computer Science  ·  Final Year Research Project  ·  2026", {
        x: 0.65, y: 6.65, w: 10, h: 0.4, fontSize: 11.5, color: C.slateLight, fontFace: "Calibri", margin: 0,
    });
}

// ═══════════════════════════════════════════════════════════════════════
// SLIDE 2 — AGENDA
// ═══════════════════════════════════════════════════════════════════════
{
    const s = pres.addSlide();
    s.background = { color: C.white };
    sectionTag(s, "Agenda");
    titleBlock(s, "What We'll Cover Today", "A structured walkthrough of all four project objectives and where we stand", 0.95);

    const items = [
        ["target", "Project Vision & Architecture", "The problem, our solution, and system design"],
        ["chart", "Objective 1 — The AI Assistant", "Personalized guidance for beginner investors"],
        ["cogs", "Objective 2 — Agentic Workflows", "Real-time scraping + automated recommendations"],
        ["users", "Objective 3 — User Satisfaction", "Trust, usability & feedback from real investors"],
        ["scale", "Objective 4 — Performance Benchmarking", "AI system vs. traditional research methods"],
        ["tie", "Team Contributions & Roadmap", "Individual work split and path to final submission"],
    ];
    const colW = (PW - 1.2 - 0.5) / 2, rowH = 1.35;
    items.forEach((it, i) => {
        const col = i % 2, row = Math.floor(i / 2);
        const x = 0.6 + col * (colW + 0.5);
        const y = 2.15 + row * (rowH + 0.18);
        s.addShape(pres.shapes.ROUNDED_RECTANGLE, {
            x, y, w: colW, h: rowH, rectRadius: 0.12, fill: { color: C.ice }, line: { type: "none" },
            shadow: freshShadow(0.08, 10, 2),
        });
        s.addShape(pres.shapes.OVAL, { x: x + 0.28, y: y + rowH / 2 - 0.34, w: 0.68, h: 0.68, fill: { color: C.navy }, line: { type: "none" } });
        s.addImage({ path: ICON(it[0], "FFFFFF"), x: x + 0.44, y: y + rowH / 2 - 0.18, w: 0.36, h: 0.36 });
        s.addText(it[1], {
            x: x + 1.15, y: y + 0.18, w: colW - 1.3, h: 0.42, fontSize: 14.5, bold: true, color: C.navy,
            fontFace: "Calibri", margin: 0,
        });
        s.addText(it[2], {
            x: x + 1.15, y: y + 0.62, w: colW - 1.3, h: 0.6, fontSize: 11, color: C.slate,
            fontFace: "Calibri", margin: 0, lineSpacingMultiple: 1.15,
        });
    });
    addFooter(s, 2);
}

// ═══════════════════════════════════════════════════════════════════════
// SLIDE 3 — PROBLEM & VISION
// ═══════════════════════════════════════════════════════════════════════
{
    const s = pres.addSlide();
    s.background = { color: C.white };
    sectionTag(s, "Project Vision");
    titleBlock(s, "Why InvestAI?", "Bridging the knowledge gap for first-time CSE investors", 0.95);

    // Left: problem
    const lx = 0.6, lw = 5.9;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, {
        x: lx, y: 2.15, w: lw, h: 4.55, rectRadius: 0.14, fill: { color: "FDF3EE" }, line: { type: "none" },
        shadow: freshShadow(0.07, 10, 2),
    });
    s.addImage({ path: ICON("warn", "F5B942"), x: lx + 0.35, y: 2.5, w: 0.5, h: 0.5 });
    s.addText("The Problem", { x: lx + 1.0, y: 2.55, w: lw - 1.3, h: 0.42, fontSize: 18, bold: true, color: C.navy, fontFace: "Cambria", margin: 0 });
    const probs = [
        "Beginner investors in Sri Lanka lack accessible, personalized financial education",
        "Manually researching CSE stocks & news is slow, fragmented, and overwhelming",
        "Generic robo-advisors don't adapt to individual risk tolerance or local market context",
        "No affordable tool combines real-time data with plain-language investment guidance",
    ];
    s.addText(probs.map(p => ({ text: p, options: { bullet: { code: "2022" }, breakLine: true, paraSpaceAfter: 12 } })), {
        x: lx + 0.4, y: 3.25, w: lw - 0.8, h: 3.3, fontSize: 13, color: C.ink, fontFace: "Calibri", margin: 0, valign: "top",
    });

    // Right: vision
    const rx = 6.85, rw = 5.9;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, {
        x: rx, y: 2.15, w: rw, h: 4.55, rectRadius: 0.14, fill: { color: C.navy }, line: { type: "none" },
        shadow: freshShadow(0.1, 12, 3),
    });
    s.addImage({ path: ICON("bulb", "F5B942"), x: rx + 0.35, y: 2.5, w: 0.5, h: 0.5 });
    s.addText("Our Solution", { x: rx + 1.0, y: 2.55, w: rw - 1.3, h: 0.42, fontSize: 18, bold: true, color: C.white, fontFace: "Cambria", margin: 0 });
    const sols = [
        "An agentic AI assistant that reasons over live CSE market data & news",
        "Personalized guidance based on each user's risk profile and goals",
        "Automated scraping + sentiment analysis for timely, data-backed insights",
        "A mobile-first experience built for first-time, everyday investors",
    ];
    s.addText(sols.map(p => ({ text: p, options: { bullet: { code: "2022" }, breakLine: true, paraSpaceAfter: 12 } })), {
        x: rx + 0.4, y: 3.25, w: rw - 0.8, h: 3.3, fontSize: 13, color: C.iceBlue, fontFace: "Calibri", margin: 0, valign: "top",
    });

    addFooter(s, 3);
}

// ═══════════════════════════════════════════════════════════════════════
// SLIDE 4 — SYSTEM ARCHITECTURE
// ═══════════════════════════════════════════════════════════════════════
{
    const s = pres.addSlide();
    s.background = { color: C.ice };
    sectionTag(s, "System Design");
    titleBlock(s, "System Architecture", "How the mobile app, backend services, and AI pipeline work together", 0.95);

    const boxes = [
        { icon: "mobile", label: "Mobile App", sub: "React Native + Expo", x: 0.6 },
        { icon: "server", label: "FastAPI Backend", sub: "REST + SSE Streaming", x: 3.55 },
        { icon: "robot", label: "AI Agent Layer", sub: "Tool-calling · RAG", x: 6.5 },
        { icon: "database", label: "Supabase (Postgres)", sub: "Auth · pgvector · Data", x: 9.45 },
    ];
    const bw = 2.85, by = 2.5, bh = 1.55;
    boxes.forEach((b) => {
        s.addShape(pres.shapes.ROUNDED_RECTANGLE, {
            x: b.x, y: by, w: bw, h: bh, rectRadius: 0.12, fill: { color: C.white }, line: { color: C.cardLine, width: 1 },
            shadow: freshShadow(0.08, 10, 2),
        });
        s.addShape(pres.shapes.OVAL, { x: b.x + bw / 2 - 0.32, y: by + 0.18, w: 0.64, h: 0.64, fill: { color: C.navy }, line: { type: "none" } });
        s.addImage({ path: ICON(b.icon, "FFFFFF"), x: b.x + bw / 2 - 0.17, y: by + 0.33, w: 0.34, h: 0.34 });
        s.addText(b.label, { x: b.x, y: by + 0.9, w: bw, h: 0.32, fontSize: 12.5, bold: true, color: C.navy, align: "center", fontFace: "Calibri", margin: 0 });
        s.addText(b.sub, { x: b.x, y: by + 1.2, w: bw, h: 0.3, fontSize: 10, color: C.slate, align: "center", fontFace: "Calibri", margin: 0 });
    });
    // arrows
    [0.6 + bw, 3.55 + bw, 6.5 + bw].forEach((ax) => {
        s.addShape(pres.shapes.RIGHT_ARROW, { x: ax + 0.02, y: by + bh / 2 - 0.09, w: 0.66, h: 0.18, fill: { color: C.iceBlueMid }, line: { type: "none" } });
    });

    // Bottom row — supporting services
    const svc = [
        { icon: "cloud", label: "Celery + Redis", sub: "Scheduled scraping & rules engine" },
        { icon: "chart", label: "CSE Scraper + Sentiment", sub: "Live prices, news, VADER scoring" },
        { icon: "shield", label: "Supabase Auth + OTP", sub: "Secure registration & verification" },
        { icon: "bell", label: "Firebase Cloud Messaging", sub: "Real-time push notifications" },
    ];
    const sw = 2.85, sy = 4.75, shh = 1.7;
    svc.forEach((v, i) => {
        const x = 0.6 + i * (sw + 0.25);
        s.addShape(pres.shapes.ROUNDED_RECTANGLE, {
            x, y: sy, w: sw, h: shh, rectRadius: 0.12, fill: { color: C.navyLight }, line: { type: "none" },
            shadow: freshShadow(0.08, 10, 2),
        });
        s.addImage({ path: ICON(v.icon, "FFFFFF"), x: x + 0.22, y: sy + 0.22, w: 0.38, h: 0.38 });
        s.addText(v.label, { x: x + 0.22, y: sy + 0.68, w: sw - 0.44, h: 0.36, fontSize: 12, bold: true, color: C.white, fontFace: "Calibri", margin: 0 });
        s.addText(v.sub, { x: x + 0.22, y: sy + 1.05, w: sw - 0.44, h: 0.58, fontSize: 9.5, color: C.iceBlue, fontFace: "Calibri", margin: 0, lineSpacingMultiple: 1.15 });
    });

    addFooter(s, 4);
}

// ═══════════════════════════════════════════════════════════════════════
// SLIDE 5 — OBJECTIVES DASHBOARD (overview of all 4 with mini bars)
// ═══════════════════════════════════════════════════════════════════════
{
    const s = pres.addSlide();
    s.background = { color: C.white };
    sectionTag(s, "Progress Snapshot");
    titleBlock(s, "Four Objectives, One Roadmap", "High-level progress across all research objectives as of Phase 2", 0.95);

    const objs = [
        { n: "01", t: "Build the AI Investment Assistant", pct: 70, color: C.teal, icon: "robot" },
        { n: "02", t: "Evaluate Agentic Workflows & Scraping", pct: 55, color: C.teal, icon: "cogs" },
        { n: "03", t: "Assess User Satisfaction & Trust", pct: 20, color: C.gold, icon: "users" },
        { n: "04", t: "Benchmark vs. Traditional Methods", pct: 20, color: C.gold, icon: "scale" },
    ];
    const rowH = 1.05, startY = 2.25;
    objs.forEach((o, i) => {
        const y = startY + i * (rowH + 0.14);
        s.addShape(pres.shapes.ROUNDED_RECTANGLE, {
            x: 0.6, y, w: PW - 1.2, h: rowH, rectRadius: 0.12, fill: { color: C.ice }, line: { type: "none" },
            shadow: freshShadow(0.06, 8, 2),
        });
        s.addText(o.n, { x: 0.85, y, w: 0.8, h: rowH, fontSize: 26, bold: true, color: C.iceBlueMid, fontFace: "Cambria", valign: "middle", margin: 0 });
        s.addShape(pres.shapes.OVAL, { x: 1.7, y: y + rowH / 2 - 0.24, w: 0.48, h: 0.48, fill: { color: C.navy }, line: { type: "none" } });
        s.addImage({ path: ICON(o.icon, "FFFFFF"), x: 1.82, y: y + rowH / 2 - 0.12, w: 0.24, h: 0.24 });
        s.addText(o.t, { x: 2.4, y: y + 0.13, w: 5.1, h: 0.5, fontSize: 14, bold: true, color: C.navy, fontFace: "Calibri", valign: "middle", margin: 0 });
        progressBar(s, 7.75, y + rowH / 2 - 0.11, 4.1, o.pct, o.color);
        s.addText(o.pct + "%", { x: 11.95, y, w: 0.7, h: rowH, fontSize: 16, bold: true, color: o.color, align: "right", valign: "middle", fontFace: "Calibri", margin: 0 });
    });

    addFooter(s, 5);
}

// ═══════════════════════════════════════════════════════════════════════
// SLIDE TEMPLATE — Objective Detail
// ═══════════════════════════════════════════════════════════════════════
function objectiveSlide({ num, title, statement, pct, barColor, completed, inProgress, next, icon }) {
    const s = pres.addSlide();
    s.background = { color: C.white };
    sectionTag(s, `Objective ${num}`);

    s.addText(title, { x: 0.6, y: 0.9, w: PW - 1.2, h: 0.6, fontSize: 27, bold: true, color: C.navy, fontFace: "Cambria", margin: 0 });
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, {
        x: 0.6, y: 1.55, w: PW - 1.2, h: 0.62, rectRadius: 0.1, fill: { color: C.navy }, line: { type: "none" },
    });
    s.addText(`"${statement}"`, {
        x: 0.85, y: 1.55, w: PW - 1.7, h: 0.62, fontSize: 12, italic: true, color: C.iceBlue,
        fontFace: "Calibri", valign: "middle", margin: 0,
    });

    // progress row
    s.addText("Overall Progress", { x: 0.6, y: 2.35, w: 2, h: 0.3, fontSize: 11, bold: true, color: C.slate, fontFace: "Calibri", margin: 0 });
    progressBar(s, 0.6, 2.68, 9.1, pct, barColor);
    s.addText(pct + "%", { x: 9.85, y: 2.4, w: 1, h: 0.4, fontSize: 18, bold: true, color: barColor, fontFace: "Calibri", margin: 0 });

    // three columns: completed / in progress / next
    const colY = 3.25, colH = 3.75, colW = 3.95, gap = 0.2;
    const cols = [
        { label: "Completed", color: C.teal, icon: "check", items: completed },
        { label: "In Progress", color: C.gold, icon: "cogs", items: inProgress },
        { label: "Next Steps", color: C.navyLight, icon: "route", items: next },
    ];
    cols.forEach((c, i) => {
        const x = 0.6 + i * (colW + gap);
        s.addShape(pres.shapes.ROUNDED_RECTANGLE, {
            x, y: colY, w: colW, h: colH, rectRadius: 0.12, fill: { color: C.ice }, line: { type: "none" },
            shadow: freshShadow(0.06, 8, 2),
        });
        s.addShape(pres.shapes.OVAL, { x: x + 0.22, y: colY + 0.2, w: 0.42, h: 0.42, fill: { color: c.color }, line: { type: "none" } });
        s.addImage({ path: ICON(c.icon, "FFFFFF"), x: x + 0.32, y: colY + 0.3, w: 0.22, h: 0.22 });
        s.addText(c.label, { x: x + 0.75, y: colY + 0.2, w: colW - 0.9, h: 0.42, fontSize: 14.5, bold: true, color: C.navy, fontFace: "Calibri", valign: "middle", margin: 0 });
        s.addText(c.items.map(t => ({ text: t, options: { bullet: { code: "2022" }, breakLine: true, paraSpaceAfter: 8 } })), {
            x: x + 0.28, y: colY + 0.78, w: colW - 0.56, h: colH - 0.95, fontSize: 10.6, color: C.ink,
            fontFace: "Calibri", margin: 0, valign: "top", lineSpacingMultiple: 1.08,
        });
    });

    return s;
}

// SLIDE 6 — Objective 1 detail
{
    const s = objectiveSlide({
        num: 1,
        title: "Build the AI Investment Assistant",
        statement: "To develop an AI-powered investment assistant that delivers personalized financial education and investment guidance tailored to beginner investors in the Sri Lankan stock market.",
        pct: 70,
        barColor: C.teal,
        completed: [
            "15+ mobile screens built: Home, Chat, Portfolio, Watchlist, Learn, Auth flow, Assessment",
            "FastAPI chat router with SSE streaming architecture",
            "Database schema: users, portfolios, chat sessions, risk profiles",
            "Supabase Auth: registration, OTP verification, login, password reset",
        ],
        inProgress: [
            "Wiring the agentic AI reasoning loop into the chat backend",
            "Connecting the mobile Chat screen to live backend responses",
            "Risk-profiling quiz results feeding into personalized advice",
            "JWT verification hardening for secure sessions",
        ],
        next: [
            "Complete tool-calling loop (stock data, news, portfolio tools)",
            "Full end-to-end: Register → Assess Risk → Chat → Recommend",
            "Add Sinhala / Tamil language support",
            "Polish onboarding & personalization UX",
        ],
    });
    addFooter(s, 6);
}

// SLIDE 7 — Objective 1 UI showcase
{
    const s = pres.addSlide();
    s.background = { color: C.white };
    sectionTag(s, "Objective 1 · UI Showcase");
    titleBlock(s, "Product Walkthrough", "Core screens built for the beginner-investor experience", 0.95);

    const shots = ["Home Dashboard", "AI Chat Assistant", "Portfolio Tracker", "Onboarding & Auth"];
    const gw = 2.9, gap = 0.22, gy = 2.15, gh = 4.6;
    shots.forEach((label, i) => {
        const x = 0.6 + i * (gw + gap);
        uiPlaceholder(s, x, gy, gw, gh, label);
    });
    addFooter(s, 7);
}

// SLIDE 8 — Objective 2 detail
{
    const s = objectiveSlide({
        num: 2,
        title: "Evaluate Agentic Workflows & Live Data",
        statement: "To evaluate the effectiveness of agentic workflows combined with real-time web scraping data in generating accurate and timely investment recommendations.",
        pct: 55,
        barColor: C.teal,
        completed: [
            "CSE market data scraper integrated with the exchange's live trade API",
            "News scraper across 3 financial sources with deduplication",
            "VADER sentiment analysis pipeline for headlines & summaries",
            "Celery + Redis task queue with scheduled Beat jobs",
            "pgvector migration for semantic (RAG) search over news",
        ],
        inProgress: [
            "Automated investment-rules checker (price / % change alerts)",
            "Deploying Celery worker + beat on a persistent schedule",
            "Capturing scrape success-rate & latency metrics",
        ],
        next: [
            "Run pipeline continuously for 2+ weeks to gather evaluation data",
            "Compare AI-generated recommendations against actual price moves",
            "Document accuracy & timeliness findings for the report",
        ],
    });
    addFooter(s, 8);
}

// SLIDE 8b — Objective 2 workflow diagram
{
    const s = pres.addSlide();
    s.background = { color: C.ice };
    sectionTag(s, "Objective 2 · Pipeline");
    titleBlock(s, "Agentic Data Pipeline", "From live market data to AI-ready insight, on an automated schedule", 0.95);

    const steps = [
        { icon: "cloud", label: "Scheduled Trigger", sub: "Celery Beat, every 15 min" },
        { icon: "search", label: "Scrape CSE + News", sub: "Live prices & headlines" },
        { icon: "flask", label: "Sentiment Scoring", sub: "VADER analysis" },
        { icon: "database", label: "Store & Embed", sub: "Postgres + pgvector" },
        { icon: "robot", label: "Agent Retrieval", sub: "RAG-powered answers" },
    ];
    const sw = 2.15, sy = 2.6, sh = 1.9, gap = 0.28;
    const totalW = steps.length * sw + (steps.length - 1) * gap;
    const startX = (PW - totalW) / 2;
    steps.forEach((st, i) => {
        const x = startX + i * (sw + gap);
        s.addShape(pres.shapes.ROUNDED_RECTANGLE, {
            x, y: sy, w: sw, h: sh, rectRadius: 0.12, fill: { color: C.white }, line: { color: C.cardLine, width: 1 },
            shadow: freshShadow(0.08, 10, 2),
        });
        s.addShape(pres.shapes.OVAL, { x: x + sw / 2 - 0.3, y: sy + 0.22, w: 0.6, h: 0.6, fill: { color: C.navy }, line: { type: "none" } });
        s.addImage({ path: ICON(st.icon, "FFFFFF"), x: x + sw / 2 - 0.16, y: sy + 0.36, w: 0.32, h: 0.32 });
        s.addText(String(i + 1), { x: x + sw - 0.42, y: sy + 0.08, w: 0.32, h: 0.32, fontSize: 11, bold: true, color: C.gold, align: "center", fontFace: "Calibri", margin: 0 });
        s.addText(st.label, { x: x + 0.1, y: sy + 0.95, w: sw - 0.2, h: 0.45, fontSize: 12, bold: true, color: C.navy, align: "center", fontFace: "Calibri", margin: 0 });
        s.addText(st.sub, { x: x + 0.1, y: sy + 1.38, w: sw - 0.2, h: 0.45, fontSize: 9.5, color: C.slate, align: "center", fontFace: "Calibri", margin: 0, lineSpacingMultiple: 1.1 });
        if (i < steps.length - 1) {
            s.addShape(pres.shapes.RIGHT_ARROW, { x: x + sw + 0.02, y: sy + sh / 2 - 0.09, w: gap - 0.04, h: 0.18, fill: { color: C.iceBlueMid }, line: { type: "none" } });
        }
    });

    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 1.4, y: 5.1, w: PW - 2.8, h: 0.95, rectRadius: 0.12, fill: { color: C.navyLight }, line: { type: "none" } });
    s.addImage({ path: ICON("bulb", "F5B942"), x: 1.65, y: 5.35, w: 0.42, h: 0.42 });
    s.addText("Engineering win: fixed the CSE trade-summary integration to pull directly from the exchange's live JSON API — removing brittle HTML scraping and improving data reliability.", {
        x: 2.25, y: 5.15, w: PW - 4.1, h: 0.85, fontSize: 11.5, color: C.white, fontFace: "Calibri", valign: "middle", margin: 0, italic: true,
    });

    addFooter(s, 9);
}

// SLIDE 9 — Objective 3 detail
{
    const s = objectiveSlide({
        num: 3,
        title: "Assess User Satisfaction & Trust",
        statement: "To assess user satisfaction, trust, and perceived usefulness of the AI assistant, including its automated investment features, through usability testing and user feedback from beginner investors.",
        pct: 20,
        barColor: C.gold,
        completed: [
            "Usability testing plan drafted (SUS + trust questionnaire)",
            "Target participant profile defined: first-time CSE investors",
        ],
        inProgress: [
            "Stabilizing the core chat + dashboard flow ahead of testing",
            "Preparing test scripts and consent / feedback forms",
        ],
        next: [
            "Recruit 8–10 beginner-investor participants",
            "Run moderated usability sessions once Objective 1 flow is stable",
            "Collect System Usability Scale (SUS) scores + qualitative feedback",
            "Analyze trust & perceived-usefulness results for the final report",
        ],
    });
    addFooter(s, 10);
}

// SLIDE 10 — Objective 4 detail
{
    const s = objectiveSlide({
        num: 4,
        title: "Benchmark vs. Traditional Research Methods",
        statement: "To measure and compare the system's technical performance, including data accuracy, response time, and reliability, against traditional stock research methods.",
        pct: 20,
        barColor: C.gold,
        completed: [
            "Benchmark methodology outlined (response time, data freshness, accuracy)",
            "Baseline traditional-method comparison group identified (manual CSE lookup)",
        ],
        inProgress: [
            "Designing a lightweight request-timing / logging middleware",
            "Defining accuracy metrics for scraped vs. official CSE data",
        ],
        next: [
            "Instrument API response-time & data-freshness logging",
            "Run side-by-side trials: AI assistant vs. manual research",
            "Compile comparative results into the final evaluation report",
        ],
    });
    addFooter(s, 11);
}

// SLIDE 11 — OVERALL PROGRESS (dark, big bars)
{
    const s = pres.addSlide();
    s.background = { color: C.navyDeep };
    s.addShape(pres.shapes.OVAL, { x: 10.5, y: -2, w: 6, h: 6, fill: { color: C.navyLight, transparency: 60 }, line: { type: "none" } });

    s.addShape(pres.shapes.ROUNDED_RECTANGLE, {
        x: 0.6, y: 0.55, w: 2.7, h: 0.4, rectRadius: 0.2, fill: { color: C.tealLight, transparency: 82 }, line: { color: C.tealLight, width: 1 },
    });
    s.addText("PROGRESS SUMMARY", { x: 0.6, y: 0.55, w: 2.7, h: 0.4, fontSize: 10.5, bold: true, color: C.tealLight, align: "center", valign: "middle", fontFace: "Calibri", charSpacing: 1, margin: 0 });
    s.addText("Where InvestAI Stands Today", { x: 0.6, y: 1.05, w: 10, h: 0.65, fontSize: 30, bold: true, color: C.white, fontFace: "Cambria", margin: 0 });

    const rows = [
        { t: "Objective 1 — AI Assistant", pct: 70 },
        { t: "Objective 2 — Agentic Workflows & Scraping", pct: 55 },
        { t: "Objective 3 — User Satisfaction", pct: 20 },
        { t: "Objective 4 — Performance Benchmarking", pct: 20 },
    ];
    const startY = 2.05, rh = 0.62;
    rows.forEach((r, i) => {
        const y = startY + i * (rh + 0.24);
        s.addText(r.t, { x: 0.65, y: y - 0.02, w: 5.9, h: 0.35, fontSize: 13, bold: true, color: C.white, fontFace: "Calibri", margin: 0 });
        progressBar(s, 0.65, y + 0.32, 8.6, r.pct, r.pct >= 40 ? C.tealLight : C.gold, "13324A");
        s.addText(r.pct + "%", { x: 9.4, y: y - 0.02, w: 0.9, h: 0.68, fontSize: 20, bold: true, color: r.pct >= 40 ? C.tealLight : C.gold, fontFace: "Calibri", valign: "middle", margin: 0 });
    });

    // Big stat callout
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 10.7, y: 2.05, w: 2.05, h: 4.55, rectRadius: 0.14, fill: { color: C.navyLight }, line: { type: "none" }, shadow: freshShadow(0.15, 14, 4) });
    s.addText("41%", { x: 10.7, y: 2.5, w: 2.05, h: 0.9, fontSize: 40, bold: true, color: C.tealLight, align: "center", fontFace: "Cambria", margin: 0 });
    s.addText("Overall Weighted\nProgress", { x: 10.8, y: 3.35, w: 1.85, h: 0.65, fontSize: 10.5, color: C.iceBlue, align: "center", fontFace: "Calibri", margin: 0 });
    s.addShape(pres.shapes.LINE, { x: 10.95, y: 4.15, w: 1.55, h: 0, line: { color: "2A4A66", width: 1 } });
    s.addText("80%", { x: 10.7, y: 4.35, w: 2.05, h: 0.7, fontSize: 30, bold: true, color: C.white, align: "center", fontFace: "Cambria", margin: 0 });
    s.addText("UI / UX Layer\nComplete", { x: 10.8, y: 5.0, w: 1.85, h: 0.6, fontSize: 10.5, color: C.iceBlue, align: "center", fontFace: "Calibri", margin: 0 });
    s.addShape(pres.shapes.LINE, { x: 10.95, y: 5.75, w: 1.55, h: 0, line: { color: "2A4A66", width: 1 } });
    s.addText("On Track", { x: 10.7, y: 5.9, w: 2.05, h: 0.5, fontSize: 15, bold: true, color: C.gold, align: "center", fontFace: "Calibri", margin: 0 });
    s.addText("for Final Demo", { x: 10.7, y: 6.3, w: 2.05, h: 0.3, fontSize: 10, color: C.iceBlue, align: "center", fontFace: "Calibri", margin: 0 });

    addFooter(s, 12, "InvestAI  |  Mid-Demonstration Phase 2");
}

// ═══════════════════════════════════════════════════════════════════════
// SLIDE 12 — TEAM CONTRIBUTIONS
// ═══════════════════════════════════════════════════════════════════════
{
    const s = pres.addSlide();
    s.background = { color: C.white };
    sectionTag(s, "Team");
    titleBlock(s, "Individual Contributions", "Each member's ownership across the InvestAI codebase", 0.95);

    const people = [
        {
            name: "S. Sanjeev", role: "Backend & Database Engineering", icon: "code",
            items: [
                "Designed the PostgreSQL schema & SQLAlchemy models (users, portfolios, chat, market data)",
                "Built FastAPI routers: auth, chat, portfolio, stocks, dashboard, notifications",
                "Implemented Supabase Auth flow: registration, OTP, login, password reset",
                "Developed the CSE scraper, sentiment pipeline, and Celery task scheduling",
                "Integrated Supabase (Postgres + pgvector) as the production backend",
                "Led frontend-backend API integration and endpoint wiring",
            ],
        },
        {
            name: "P. Sajeevan", role: "Frontend & UI Integration", icon: "mobile",
            items: [
                "Built the React Native / Expo mobile application structure",
                "Designed and implemented 15+ screens: Home, Chat, Portfolio, Watchlist, Learn",
                "Built the full authentication UI flow (Login, Register, OTP, Reset Password)",
                "Implemented the risk-profiling assessment & onboarding experience",
                "Connected UI components to backend API services",
                "Applied the InvestAI design system across all screens",
            ],
        },
    ];
    const cw = 5.95, cx0 = 0.6, cy = 2.15, ch = 4.55, gap = 0.2;
    people.forEach((p, i) => {
        const x = cx0 + i * (cw + gap);
        s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y: cy, w: cw, h: ch, rectRadius: 0.14, fill: { color: C.ice }, line: { type: "none" }, shadow: freshShadow(0.07, 10, 2) });
        s.addShape(pres.shapes.OVAL, { x: x + 0.3, y: cy + 0.3, w: 0.72, h: 0.72, fill: { color: C.navy }, line: { type: "none" } });
        s.addImage({ path: ICON(p.icon, "FFFFFF"), x: x + 0.48, y: cy + 0.48, w: 0.36, h: 0.36 });
        s.addText(p.name, { x: x + 1.2, y: cy + 0.28, w: cw - 1.4, h: 0.4, fontSize: 18, bold: true, color: C.navy, fontFace: "Cambria", margin: 0 });
        s.addText(p.role, { x: x + 1.2, y: cy + 0.68, w: cw - 1.4, h: 0.32, fontSize: 12, color: C.teal, bold: true, fontFace: "Calibri", margin: 0 });
        s.addShape(pres.shapes.LINE, { x: x + 0.3, y: cy + 1.2, w: cw - 0.6, h: 0, line: { color: C.cardLine, width: 1 } });
        s.addText(p.items.map(t => ({ text: t, options: { bullet: { code: "2022" }, breakLine: true, paraSpaceAfter: 10 } })), {
            x: x + 0.3, y: cy + 1.38, w: cw - 0.6, h: ch - 1.55, fontSize: 11.5, color: C.ink, fontFace: "Calibri", margin: 0, valign: "top", lineSpacingMultiple: 1.1,
        });
    });

    addFooter(s, 13);
}

// ═══════════════════════════════════════════════════════════════════════
// SLIDE 13 — ROADMAP TO FINAL SUBMISSION
// ═══════════════════════════════════════════════════════════════════════
{
    const s = pres.addSlide();
    s.background = { color: C.white };
    sectionTag(s, "Looking Ahead");
    titleBlock(s, "Roadmap to Final Submission", "Concrete milestones between now and the final demonstration", 0.95);

    const steps = [
        { t: "Complete Core Integration", d: "Finish agent tool-calling loop, connect chat UI to live backend, harden authentication", w: "Weeks 1–2" },
        { t: "Deploy & Stabilize Pipeline", d: "Run scraping + rules engine on schedule; fix bugs surfaced in daily use", w: "Weeks 2–3" },
        { t: "Usability Testing (Obj. 3)", d: "Recruit participants, run SUS testing, collect trust & satisfaction feedback", w: "Weeks 3–4" },
        { t: "Performance Benchmarking (Obj. 4)", d: "Log response times & data accuracy; compare against manual research baseline", w: "Weeks 4–5" },
        { t: "Final Report & Demo Prep", d: "Compile findings, polish UI, rehearse final demonstration", w: "Week 6" },
    ];
    const y0 = 2.25, rowH = 0.92;
    s.addShape(pres.shapes.LINE, { x: 1.05, y: y0 + 0.18, w: 0, h: (steps.length - 1) * rowH, line: { color: C.iceBlue, width: 3 } });
    steps.forEach((st, i) => {
        const y = y0 + i * rowH;
        s.addShape(pres.shapes.OVAL, { x: 0.85, y: y, w: 0.4, h: 0.4, fill: { color: C.navy }, line: { color: C.white, width: 2 } });
        s.addText(String(i + 1), { x: 0.85, y: y, w: 0.4, h: 0.4, fontSize: 12, bold: true, color: C.white, align: "center", valign: "middle", fontFace: "Calibri", margin: 0 });
        s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 1.55, y: y - 0.08, w: PW - 2.5, h: 0.78, rectRadius: 0.1, fill: { color: C.ice }, line: { type: "none" } });
        s.addText(st.t, { x: 1.8, y: y - 0.08, w: 4.4, h: 0.78, fontSize: 13, bold: true, color: C.navy, valign: "middle", fontFace: "Calibri", margin: 0 });
        s.addText(st.d, { x: 6.3, y: y - 0.08, w: 5.2, h: 0.78, fontSize: 10.5, color: C.slate, valign: "middle", fontFace: "Calibri", margin: 0 });
        s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: PW - 2.35, y: y + 0.1, w: 1.35, h: 0.42, rectRadius: 0.21, fill: { color: C.iceBlue }, line: { type: "none" } });
        s.addText(st.w, { x: PW - 2.35, y: y + 0.1, w: 1.35, h: 0.42, fontSize: 9.5, bold: true, color: C.navy, align: "center", valign: "middle", fontFace: "Calibri", margin: 0 });
    });

    addFooter(s, 14);
}

// ═══════════════════════════════════════════════════════════════════════
// SLIDE 14 — CLOSING
// ═══════════════════════════════════════════════════════════════════════
{
    const s = pres.addSlide();
    s.background = { color: C.navyDeep };
    s.addShape(pres.shapes.OVAL, { x: -2, y: -2.5, w: 7, h: 7, fill: { color: C.navyLight, transparency: 58 }, line: { type: "none" } });
    s.addShape(pres.shapes.OVAL, { x: 9.5, y: 3.5, w: 6.5, h: 6.5, fill: { color: C.navyLight, transparency: 64 }, line: { type: "none" } });

    s.addImage({ path: ICON("robot", "FFFFFF"), x: PW / 2 - 0.45, y: 1.75, w: 0.9, h: 0.9 });
    s.addText("Thank You", { x: 0, y: 2.75, w: PW, h: 0.9, fontSize: 42, bold: true, color: C.white, align: "center", fontFace: "Cambria", margin: 0 });
    s.addText("Questions & Discussion", { x: 0, y: 3.55, w: PW, h: 0.5, fontSize: 16, color: C.iceBlue, align: "center", fontFace: "Calibri", margin: 0 });

    s.addShape(pres.shapes.LINE, { x: PW / 2 - 1.5, y: 4.35, w: 3, h: 0, line: { color: C.navyLight, width: 1.5 } });

    s.addText([
        { text: "S. Sanjeev", options: { bold: true, color: C.white, fontSize: 13, breakLine: true } },
        { text: "Backend & Database Engineering", options: { color: C.slateLight, fontSize: 10.5 } },
    ], { x: 2.5, y: 4.65, w: 3.8, h: 0.75, align: "center", fontFace: "Calibri", margin: 0, lineSpacingMultiple: 1.25 });
    s.addText([
        { text: "P. Sajeevan", options: { bold: true, color: C.white, fontSize: 13, breakLine: true } },
        { text: "Frontend & UI Integration", options: { color: C.slateLight, fontSize: 10.5 } },
    ], { x: 7.0, y: 4.65, w: 3.8, h: 0.75, align: "center", fontFace: "Calibri", margin: 0, lineSpacingMultiple: 1.25 });

    s.addText("github.com/sanjeev200009/investment_AI", { x: 0, y: 6.55, w: PW, h: 0.35, fontSize: 11.5, color: C.tealLight, align: "center", fontFace: "Calibri", margin: 0 });
}

pres.writeFile({ fileName: "/home/claude/investai_deck/InvestAI_Mid_Demonstration.pptx" }).then(() => {
    console.log("done");
});