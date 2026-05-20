module.exports = {
  static: {
    "e-eyebrow": "Community Platform",
    "e-h1": "Your texting program, every stage",
    "e-hsub": "From first opt-in to fully integrated AI — find where you are and see what comes next.",
    "e-pEyebrow": "Guiding principles",
    "e-pH2": "What makes great text programs",
    "e-pSub": "Keep these in mind across every phase.",
    "e-cEyebrow": "Maturity curve",
    "e-cH2": "Where are you today?",
    "e-cSub": "Select a phase to see what it involves and what to focus on next.",
    "e-fH2": "Not sure where to start?",
    "e-fSub": "Your CSM can walk you through where you are and what to focus on next."
  },
  principles: [
    { t: "Audience growth never stops",       b: "It's ongoing work at every stage, not a one-time launch task." },
    { t: "Conversations beat broadcasts",     b: "Members can text back. The more you lean into that, the better your results." },
    { t: "Engagement matters more than size", b: "A smaller, active audience outperforms a large, passive one." },
    { t: "Your own pace is the right pace",   b: "No timeline required. Come back to this guide whenever you're ready." },
    { t: "Lead with value",                   b: "Give members something worth having before you ask for anything in return." },
    { t: "Every reply is a data point",       b: "First-party data members choose to share is more reliable than anything you buy." },
    { t: "Personalization compounds",         b: "Each campaign teaches you something. The next one gets more relevant." },
    { t: "Timing unlocks text's advantage",   b: "Text is your fastest channel. Use it when timing actually matters." }
  ],
  phases: [
    {
      n: "01", name: "Launch", tag: "Trust and permission", color: "oklch(0.68 0.12 250)",
      desc: "Get the channel open and give members a reason to stay from message one.",
      uc: [
        { t: "Welcome flow", body: "Confirm the opt-in, ask one question, and deliver something worth having — all within 24 hours of someone joining.", tip: "Three messages max. One welcome, one piece of value, one question that earns a reply.", res: [] },
        { t: "Announce",     body: "Let your audience know the channel is open with a short, personal video that shows there's a real person behind the number.", tip: "Post it everywhere on the same day. Treat it like a real launch.", res: [] },
        { t: "Invite",       body: "Reach your most engaged followers first — email subscribers, loyalty members — with a message that makes them feel like insiders.", tip: "Frame it as early access, not a marketing email.", res: [] }
      ]
    },
    {
      n: "02", name: "First 90 days", tag: "Acquire and onboard", color: "oklch(0.60 0.13 250)",
      desc: "Build a sending rhythm and learn what actually gets a response.",
      uc: [
        { t: "Respond and engage", body: "Reply to meaningful inbound messages. Even a short response makes members feel heard and more likely to engage again.", tip: "A one-line reply goes further than silence.", res: [] },
        { t: "Content calendar",   body: "Plan a month of messages before you send anything. Mix news, questions, behind-the-scenes moments, and time-sensitive updates.", tip: "Build around real moments — releases, events, milestones. Not made-up send dates.", res: [] },
        { t: "Keyword flows",      body: "Set up automated responses for specific words so members are immediately routed to what they're most interested in.", tip: "Promote your keywords in bios so members know they exist.", res: [] },
        { t: "Auto-responders",    body: "Automated replies for after-hours messages keep the channel feeling active when your team isn't monitoring.", tip: "Tell members when to expect a real response — it sets expectations.", res: [] }
      ]
    },
    {
      n: "03", name: "Audience growth", tag: "Expand your reach", color: "oklch(0.52 0.14 250)",
      desc: "List growth is ongoing — your existing audience is always the best place to start.",
      uc: [
        { t: "Website and pop-ups",   body: "Embed the Community sign-up module on your site where visitors are already engaged.", tip: "Place opt-ins near high-intent moments — checkout, event pages, product pages.", res: [] },
        { t: "Link in bio",           body: "Add your Community number to every bio and resurface it monthly with a short video.", tip: "Story formats convert better than feed posts for Community CTAs.", res: [] },
        { t: "Email cross-promotion", body: "A click-to-text link in your regular emails converts email subscribers who haven't joined yet.", tip: "Add your Community link to your email footer permanently.", res: [] },
        { t: "QR codes",              body: "Deploy QR codes at events, on merch, and in physical spaces with a unique keyword per placement to track sign-up origin.", tip: "Always add a short CTA next to the code. A bare QR converts far worse.", res: [] },
        { t: "Live events",           body: "PA callouts and video board content can bring in hundreds of new members at once when tied to a contest or incentive.", tip: "Ask during peak excitement — a big moment, a break, an intermission.", res: [] },
        { t: "Gated content",         body: "Require SMS opt-in to access early content, exclusive drops, or event perks to attract members who actually want to be there.", tip: "People who join for access stay. People who join for discounts leave.", res: [] }
      ]
    },
    {
      n: "04", name: "Engagement and data", tag: "Collect and act on signals", color: "oklch(0.46 0.14 250)",
      desc: "Ask questions, respond to replies, and use what you learn to make every next message more relevant.",
      uc: [
        { t: "Campaigns",   body: "Use dynamic fields and A/B testing to reach your list with messages that feel personal, not broadcast.", tip: "Always follow up with non-responders. The second touch consistently outperforms silence.", res: [] },
        { t: "Flows",       body: "Automated sequences that respond to what a member actually does — sign-up, keyword, link click — not a blast schedule.", tip: "Start with one welcome flow and one campaign follow-up. Build outward from there.", res: [] },
        { t: "Surveys",     body: "Ask one question and use the answer to route members into more relevant segments automatically.", tip: "One question at a time. Stacking questions kills completion rates.", res: [] },
        { t: "Voice notes", body: "A voice message carries tone in a way written text can't. Members who hear your voice reply at meaningfully higher rates.", tip: "Don't over-script it. A natural, slightly unpolished message outperforms a rehearsed one.", res: [] }
      ]
    },
    {
      n: "05", name: "Segmentation and AI", tag: "Personalize at scale", color: "oklch(0.40 0.14 250)",
      desc: "Send the right message to the right group and lay the groundwork for AI-assisted messaging.",
      uc: [
        { t: "Subcommunities",       body: "Build groups from keyword responses, QR origins, survey answers, and purchase behavior for more targeted messaging.", tip: "Name subcommunities by how you'll message them, not how you define them internally.", res: [] },
        { t: "Music vertical",       body: "For music clients: merch drops via Shopify, tour content via Seated or Bandsintown, and listening-based content by album or genre preference.", tip: "Tour subcommunities work best when city-specific, not regional.", res: [] },
        { t: "Brand voice for AI",   body: "Write out your brand voice — tone, vocabulary, what you'd never say — before configuring any AI responses.", tip: "Include examples of messages you'd never send. Negative examples are as useful as positive ones.", res: [] },
        { t: "AI-assisted responses", body: "Campaign analysis that shows what drove replies, and automated follow-ups that respond to intent rather than exact keywords.", tip: "Start with AI analysis. Understanding what works comes before automating it.", res: [] }
      ]
    },
    {
      n: "06", name: "Advanced engagement", tag: "Two-way data exchange", color: "oklch(0.35 0.14 250)",
      desc: "Connect Community to your stack and let data flow both ways.",
      uc: [
        { t: "Shopify",     body: "Track revenue from messages, trigger abandoned cart reminders, and enroll shoppers into your Community list at checkout.", tip: "Abandoned cart messages work best within 30–60 minutes of the abandonment.", res: [] },
        { t: "Salesforce",  body: "Sync members as contacts or leads automatically and connect to Marketing Cloud Journey Builder.", tip: "Map at least three Community fields to Salesforce to make the sync meaningfully useful.", res: [] },
        { t: "Zapier",      body: "Connect Community to 5,000+ other tools with no-code automations — a good starting point for teams without engineering resources.", tip: "Test your Zap triggers with a small audience before activating for your full list.", res: [] },
        { t: "Data import", body: "Export your member list, enrich it with CRM data, and reimport to make your segments immediately smarter.", tip: "Last purchase date and total spend are the two most useful fields to start with.", res: [] }
      ]
    },
    {
      n: "07", name: "Fully integrated AI", tag: "Value exchange and intelligence", color: "oklch(0.28 0.13 250)",
      desc: "A program that compounds — each campaign smarter than the last.",
      uc: [
        { t: "Rich messaging",    body: "WhatsApp, RCS, and Apple Messages for Business enable interactive, app-like experiences beyond standard SMS.", tip: "Only adopt a new channel because your audience is already there, not because it exists.", res: [] },
        { t: "AI chatbot",        body: "Real-time conversational AI that responds in your brand's voice — like Weber Ranch's AI bartender Tex, who learns drink preferences via text.", tip: "Start with one narrow use case the AI handles well, then expand its scope.", res: [] },
        { t: "Engagement loop",   body: "You send → you learn → you personalize → you earn more engagement. Each cycle gets more relevant and more efficient.", tip: "Document your learnings after every send. Patterns emerge over time.", res: [] },
        { t: "APIs and webhooks", body: "Keep member data current, manage subcommunity membership automatically, and trigger messages based on CRM events.", tip: "Build error handling into every webhook from day one — failures are silent without it.", res: [] },
        { t: "Metrics",           body: "Track subscriber growth, engagement rate, opt-out rate, conversion rate, and revenue per message continuously.", tip: "Opt-out rate is your most important health metric. Rising means send less, not more.", res: [] }
      ]
    }
  ]
};
