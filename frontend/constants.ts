import { InvestorId, InvestorProfile, Language, Personality } from './types';

export const INVESTOR_PROFILES: Record<InvestorId, InvestorProfile> = {
  [InvestorId.VINCENT]: {
    id: InvestorId.VINCENT,
    name: 'Vincent Vance',
    emoji: '📊',
    color: '0, 84%, 60%', // Vincent Red
    focus: 'Finance, Margins, Valuation, Profitability',
    bio: 'A ruthless financial pragmatist who cares only about the cold, hard cash. He despises high valuations without proven sales and loves royalty deals.',
    specializations: ['Valuation metrics', 'Royalty structures', 'Customer acquisition cost', 'Profit margins']
  },
  [InvestorId.MARCUS]: {
    id: InvestorId.MARCUS,
    name: 'Marcus Sterling',
    emoji: '🛡️',
    color: '217, 91%, 60%', // Marcus Blue
    focus: 'Technology, Architecture, Defensibility, Scale',
    bio: 'A tech billionaire who looks for proprietary technology, strong intellectual property, and founders who are willing to grind.',
    specializations: ['AI & SaaS architecture', 'Market defensibility', 'Scalability bottlenecks', 'Sales execution']
  },
  [InvestorId.BEATRICE]: {
    id: InvestorId.BEATRICE,
    name: 'Beatrice Belmont',
    emoji: '📈',
    color: '142, 71%, 45%', // Beatrice Green
    focus: 'Branding, Leadership, Marketing, Trust',
    bio: 'A real estate mogul who invests in people rather than just numbers. Beatrice values raw passion, authenticity, and a founder\'s ability to bounce back from failure.',
    specializations: ['Founder dynamics', 'Brand storytelling', 'PR & marketing strategy', 'Team culture']
  },
  [InvestorId.LEONA]: {
    id: InvestorId.LEONA,
    name: 'Leona Lyonne',
    emoji: '👥',
    color: '271, 81%, 66%', // Leona Purple
    focus: 'Go-To-Market, Operations, Mass Appeal, Growth',
    bio: 'An expert in mass consumer appeal. She looks for clear utility, retail readiness, and operational efficiency.',
    specializations: ['Mass market appeal', 'Retail distribution', 'Packaging & design', 'Supply chain logistics']
  }
};

export const STARTUP_PRESETS = {
  [Language.EN]: {
    startupName: 'Nebula AI',
    founderName: 'Alex Rivera',
    sector: 'AI / B2B SaaS',
    askAmount: '$1.5M',
    askEquity: 15,
    description: 'A smart AI recruitment assistant that pre-screens technical candidates via automated real-time coding conversations, reducing time-to-hire by 75%.'
  },
  [Language.JA]: {
    startupName: 'ネビュラAI (Nebula AI)',
    founderName: 'リベラ・アレックス (Alex Rivera)',
    sector: 'AI / B2B SaaS',
    askAmount: '1.5億円',
    askEquity: 15,
    description: '自動化されたリアルタイムのコーディング対話を通じて技術候補者を事前スクリーニングし、採用時間を75%削減するスマートなAI採用アシスタント。'
  }
};

export const PERSONALITY_DESCRIPTIONS = {
  [Language.EN]: {
    [Personality.EXCELLENT]: 'Flawless, highly confident, data-driven, and handles tough questions with ease.',
    [Personality.GOOD]: 'Strong, strategic, and clear, with solid business metrics.',
    [Personality.AVERAGE]: 'Balanced but standard pitch delivery without extreme highlights.',
    [Personality.WEAK]: 'Struggles with numbers, easily flustered, and gives vague answers.',
    [Personality.POOR]: 'Unprepared, lacks clear metrics, and gets defensive under pressure.',
    [Personality.VERY_POOR]: 'Extremely flustered, completely misses key financial metrics, and panics.'
  },
  [Language.JA]: {
    [Personality.EXCELLENT]: '完璧で、非常に自信に満、データ主導で、厳しい質問にも容易に対処します。',
    [Personality.GOOD]: '強力で、戦略的かつ明確であり、強固なビジネス指標を持っています。',
    [Personality.AVERAGE]: 'バランスは取れているが、極端なハイライトのない標準的なピッチ。',
    [Personality.WEAK]: '数字に苦しみ、簡単に慌ててしまい、曖昧な回答をします。',
    [Personality.POOR]: '準備不足で、明確な指標を欠き、プレッシャーの下で防御的になります。',
    [Personality.VERY_POOR]: '極度に慌てふためき、主要な財務指標を完全に欠き、パニックに陥ります。'
  }
};

export const TRANSLATIONS = {
  [Language.EN]: {
    title: 'VC Shark Tank Simulator',
    subtitle: 'Multi-Agent Venture Capital Pitch Orchestrator',
    setupTitle: 'Simulation Setup',
    realMode: 'Real Entrepreneur',
    realModeDesc: 'Type or speak your own pitches and answers.',
    aiMode: 'AI Entrepreneur',
    aiModeDesc: 'Watch an AI founder agent pitch on autopilot.',
    rounds: 'Rounds of Questioning',
    roundsDesc: '1 round = each active investor agent asks exactly 1 question.',
    language: 'Language',
    startupDetails: 'Startup Details',
    startupName: 'Startup Name',
    founderName: 'Founder Name',
    sector: 'Sector / Industry',
    fundingAsk: 'Funding Ask',
    equityOffer: 'Equity Offer (%)',
    description: 'Elevator Pitch / Description',
    aiPersonality: 'AI Founder Personality',
    customTraits: 'Custom Traits',
    apiActive: 'API Connected',
    apiMissing: 'API Key Missing (Using Local Fallbacks)',
    startSim: 'Launch Simulation',
    restart: 'Restart',
    confirmRestart: 'Are you sure you want to end this pitch simulation and restart?',
    activeDashboard: 'Active Simulation Dashboard',
    round: 'Round',
    questions: 'Questions',
    modelBadge: 'Gemini 3.5 Flash',
    investorPanel: 'The Investor Panel',
    confidence: 'Confidence',
    questionsCount: 'Questions Asked',
    analyzeNotes: 'Analyze Notes',
    thinking: 'Evaluating...',
    out: 'OUT',
    invest: 'INVEST',
    chatFeed: 'Interactive Conversation Feed',
    typePlaceholder: 'Type your pitch response...',
    typeCounter: 'Type counter-proposal...',
    listening: 'Listening...',
    bargainingComplete: 'Bargaining complete.',
    speakBtn: 'Speak',
    aiAssistBtn: 'AI Assist',
    autoplay: 'Autoplay',
    mute: 'Mute',
    unmute: 'Unmute',
    midPitchOffer: 'Mid-Pitch Offer Alert!',
    acceptDeal: 'Accept Deal',
    keepListening: 'Keep Listening',
    bargainingPhase: 'Bargaining Phase',
    activeOffers: 'Active Offers',
    walkAway: 'Walk Away',
    walkAwayDesc: 'Decline all offers and leave empty-handed.',
    reportTitle: 'VC Evaluation Memo',
    readinessScore: 'VC Readiness Score',
    executiveSummary: 'Executive Summary',
    agreedTermSheet: 'Agreed Term Sheet',
    noDeal: 'No Deal Reached',
    riskAssessment: 'Risk Assessment Grid',
    strategicStrengths: 'Strategic Strengths',
    growthRoadmap: 'Actionable Growth Roadmap',
    printReport: 'Print Report',
    backToSetup: 'Back to Setup',
    strengths: 'Observed Strengths',
    weaknesses: 'Observed Weaknesses',
    risks: 'Risk Warnings',
    bio: 'Biography',
    specializations: 'Specializations',
    close: 'Close',
    systemAlert: 'System Alert',
    jointOffer: 'Joint Offer',
    counterOffer: 'Counter Offer',
    submitCounter: 'Submit Counter-Offer',
    counterPlaceholder: 'e.g., I want $1.5M for 12% equity instead.',
    agentMonitor: 'Antigravity SDK Multi-Agent Monitor',
    agentStatus: 'Agent Status',
    agentFounder: 'Founder Agent',
    agentVincent: 'Vincent Agent',
    agentMarcus: 'Marcus Agent',
    agentBeatrice: 'Beatrice Agent',
    agentLeona: 'Leona Agent'
  },
  [Language.JA]: {
    title: 'VC シャークタンク・シミュレーター',
    subtitle: 'マルチエージェント投資ピッチ・オーケストレーター',
    setupTitle: 'シミュレーション設定',
    realMode: 'リアル起業家モード',
    realModeDesc: '自分でピッチや回答を入力または発言します。',
    aiMode: 'AI起業家モード',
    aiModeDesc: 'AI創業者が自動操縦でピッチするのを見守ります。',
    rounds: '質問ラウンド数',
    roundsDesc: '1ラウンド = 各アクティブな投資家が1つ質問します。',
    language: '言語',
    startupDetails: 'スタートアップの詳細',
    startupName: 'スタートアップ名',
    founderName: '創業者名',
    sector: 'セクター / 業界',
    fundingAsk: '希望調達額',
    equityOffer: '放出株式比率 (%)',
    description: 'エレベーターピッチ / 説明',
    aiPersonality: 'AI創業者の性格',
    customTraits: 'カスタム特性',
    apiActive: 'API 接続中',
    apiMissing: 'APIキー未設定 (ローカルフォールバックを使用)',
    startSim: 'シミュレーション開始',
    restart: '再起動',
    confirmRestart: 'このピッチシミュレーションを終了して再起動してもよろしいですか？',
    activeDashboard: 'アクティブ・シミュレーション・ダッシュボード',
    round: 'ラウンド',
    questions: '質問数',
    modelBadge: 'Gemini 3.5 Flash',
    investorPanel: '投資家パネル',
    confidence: '確信度',
    questionsCount: '質問数',
    analyzeNotes: 'メモを分析',
    thinking: '評価中...',
    out: '退出 (OUT)',
    invest: '投資 (INVEST)',
    chatFeed: 'インタラクティブ対話フィード',
    typePlaceholder: 'ピッチの回答を入力してください...',
    typeCounter: '対案を入力してください...',
    listening: '聞き取り中...',
    bargainingComplete: '交渉完了。',
    speakBtn: '話す',
    aiAssistBtn: 'AIアシスト',
    autoplay: '自動再生',
    mute: '消音',
    unmute: '音量オン',
    midPitchOffer: 'ピッチ途中オファー発生！',
    acceptDeal: 'オファーを受け入れる',
    keepListening: '交渉を続ける',
    bargainingPhase: '交渉フェーズ',
    activeOffers: '有効なオファー',
    walkAway: '辞退して退出',
    walkAwayDesc: 'すべてのオファーを断り、手ぶらで立ち去ります。',
    reportTitle: 'VC評価メモ',
    readinessScore: 'VC投資適格スコア',
    executiveSummary: 'エグゼクティブ・サマリー',
    agreedTermSheet: '合意された投資条件',
    noDeal: '合意に至らず',
    riskAssessment: 'リスク評価グリッド',
    strategicStrengths: '戦略的強み',
    growthRoadmap: '実行可能な成長ロードマップ',
    printReport: 'レポートを印刷',
    backToSetup: '設定に戻る',
    strengths: '観察された強み',
    weaknesses: '観察された弱み',
    risks: 'リスク警告',
    bio: '略歴',
    specializations: '専門分野',
    close: '閉じる',
    systemAlert: 'システム警告',
    jointOffer: '共同オファー',
    counterOffer: 'カウンターオファー (対案)',
    submitCounter: '対案を送信',
    counterPlaceholder: '例: 代わりに12%の株式で1.5億円を希望します。',
    agentMonitor: 'Antigravity SDK マルチエージェント・モニター',
    agentStatus: 'エージェントステータス',
    agentFounder: '創業者エージェント',
    agentVincent: 'ヴィンセント・エージェント',
    agentMarcus: 'マークス・エージェント',
    agentBeatrice: 'ベアトリス・エージェント',
    agentLeona: 'レオナ・エージェント'
  }
};

// Robust Fallback Templates for Offline/No-API Mode (Up to 10 distinct questions per investor)
export const FALLBACK_RESPONSES = {
  [Language.EN]: {
    [InvestorId.VINCENT]: {
      questions: [
        "What is your customer acquisition cost, and how quickly do I get my money back?",
        "Your valuation is insane. Why on earth is this worth that much money today?",
        "Why shouldn't I just wait for you to fail and buy your assets for pennies?",
        "Where are the margins? If you don't have a 70% gross margin, you're dead in the water.",
        "How much debt do you currently have on your balance sheet?",
        "What is your customer churn rate? Give me the exact percentage.",
        "If I give you this money, how much goes directly to your salary?",
        "Why should I do equity when I can demand a royalty of $2.00 per unit?",
        "What is your projected net income for the next fiscal year?",
        "Who is your biggest competitor, and why are they going to crush you?"
      ],
      critiques: [
        "This is a hobby, not a business. You're trying to build a museum, not a money machine.",
        "I like money, but I hate losing it. Right now, you look like a cash incinerator.",
        "The valuation makes absolutely no sense. It's a fantasy."
      ],
      offers: {
        cash: "$1.5M",
        equity: 30,
        terms: "Plus a $1.50 royalty per unit sold until I recoup $3M, then it drops to 10% equity."
      },
      exit: "I don't see a path to a 10x return here. For that reason, I'm out."
    },
    [InvestorId.MARCUS]: {
      questions: [
        "What is your proprietary technology? What stops Google or Microsoft from copying this in a weekend?",
        "How are you going to scale this sales process? Who is actually doing the cold calling?",
        "Tell me about your data pipeline. How are you training these models without getting sued?",
        "Are you a feature or a real platform? I see a hundred of these every week.",
        "What is your monthly active user growth rate over the last six months?",
        "How do you handle server latency and API scaling bottlenecks?",
        "Is your code open-source, or do you own 100% of the intellectual property?",
        "What is your customer lifetime value (LTV) compared to your CAC?",
        "How are you leveraging decentralized networks or edge computing?",
        "Who is your head of engineering, and why are they world-class?"
      ],
      critiques: [
        "You're grinding, but you're grinding in the wrong direction. Your tech stack is fragile.",
        "I love the space, but you're competing with giants who have infinite capital.",
        "If you don't know your numbers, you don't know your business. You need to wake up."
      ],
      offers: {
        cash: "$1.5M",
        equity: 20,
        terms: "Must integrate with my portfolio tech stack immediately. 20% equity, no royalties."
      },
      exit: "You're a great person, but the tech defensibility just isn't there. I'm out."
    },
    [InvestorId.BEATRICE]: {
      questions: [
        "I don't care about the tech. Tell me about your biggest failure and how you bounced back.",
        "Do you have the fire in your belly? Why should I trust you with my hard-earned money?",
        "Your branding is incredibly boring. How are you going to make people actually care about this?",
        "Who is your co-founder, and why do you work well together?",
        "What does your gut tell you about your biggest vulnerability right now?",
        "How do you handle disagreements within your leadership team?",
        "Tell me about the first person you hired and why you chose them.",
        "What is the most unconventional marketing stunt you've pulled to get users?",
        "If your company went bankrupt tomorrow, what would you do the next day?",
        "Why do you think you have the emotional resilience to survive this journey?"
      ],
      critiques: [
        "You're too slick. I don't trust people who have an answer for everything.",
        "I invest in the jockey, not the horse. Right now, you look a bit tired.",
        "I love your energy, but the business model feels like a house of cards."
      ],
      offers: {
        cash: "$1.5M",
        equity: 15,
        terms: "Requires a complete rebranding of the marketing site and 15% equity."
      },
      exit: "I just don't feel it in my gut. I need to trust my instincts. I'm out."
    },
    [InvestorId.LEONA]: {
      questions: [
        "Is this a hero or a zero? Can this be explained to a normal person in 5 seconds?",
        "What is your manufacturing cost vs. retail price? How do we scale the supply chain?",
        "Have you thought about retail distribution or QVC? This feels perfect mass market.",
        "What is your return rate? If customers don't love it, we have nothing.",
        "What is your packaging strategy? Does it pop on a crowded retail shelf?",
        "Do you have a utility patent or just a design patent on this product?",
        "How many units have you sold organically without any paid advertising?",
        "What is your plan to handle inventory management during peak holiday seasons?",
        "Can this product be easily bundled or upsold with other accessories?",
        "What is the single biggest customer complaint you've received so far?"
      ],
      critiques: [
        "This is a clever product, but it's too niche. It needs to appeal to the masses.",
        "Your packaging is terrible. We need to make it pop on a retail shelf.",
        "I can help you get this into 10,000 stores tomorrow, but you aren't ready for that volume."
      ],
      offers: {
        cash: "$1.5M",
        equity: 18,
        terms: "18% equity, plus exclusive rights to all retail and TV shopping distribution."
      },
      exit: "It's a bit too early for my distribution network. I wish you luck, but I'm out."
    }
  },
  [Language.JA]: {
    [InvestorId.VINCENT]: {
      questions: [
        "顧客獲得コスト（CAC）はいくらですか？また、私の投資資金はどれくらいで回収できますか？",
        "評価額が異常に高すぎます。なぜ今日、この事業にそれほどの価値があると言えるのですか？",
        "あなたが失敗するのを待って、破産した資産を二束三文で買い叩いた方が賢明ではないですか？",
        "粗利益率はどこにありますか？70%以上の粗利益率がなければ、ビジネスとして成り立ちません。",
        "現在、バランスシートにどれくらいの負債を抱えていますか？",
        "顧客の解約率（チャーンレート）は？正確なパーセンテージを教えてください。",
        "この資金を提供した場合、あなたの役員報酬にいくら充てられますか？",
        "株式ではなく、1ユニットあたり200円のロイヤリティを要求した方が良いのではないですか？",
        "来期の予測純利益はいくらですか？",
        "最大の競合他社はどこで、なぜ彼らがあなたを圧倒すると思いますか？"
      ],
      critiques: [
        "これはビジネスではなく、ただの趣味です。あなたはマネーマシンではなく、美術館を作ろうとしています。",
        "私はお金が大好きですが、失うことは大嫌いです。今のあなたは現金を燃やしているだけにしか見えません。",
        "この評価額は全く筋が通りません。ただのファンタジーです。"
      ],
      offers: {
        cash: "1.5億円",
        equity: 30,
        terms: "投資額の2倍（3億円）を回収するまで、販売1ユニットあたり150円のロイヤリティを支払い、その後は10%の株式を維持する。"
      },
      exit: "10倍のリターンを得る道筋が見えません。したがって、今回は見送ります（OUT）。"
    },
    [InvestorId.MARCUS]: {
      questions: [
        "独自の技術は何ですか？GoogleやMicrosoftが週末にこれをコピーするのをどうやって防ぎますか？",
        "この販売プロセスをどのようにスケールさせますか？実際にテレアポや営業を行っているのは誰ですか？",
        "データパイプラインについて教えてください。訴訟リスクを避けながら、どのようにモデルをトレーニングしていますか？",
        "これは単なる一機能ですか、それとも本物のプラットフォームですか？毎週このような提案を100件は見ています。",
        "過去6ヶ月間の月間アクティブユーザー（MAU）の成長率は？",
        "サーバーの遅延やAPIのスケーリングのボトルネックにどのように対処していますか？",
        "コードはオープンソースですか、それとも知的財産権を100%所有していますか？",
        "顧客生涯価値（LTV）と顧客獲得コスト（CAC）の比率は？",
        "分散型ネットワークやエッジコンピューティングをどのように活用していますか？",
        "開発責任者は誰で、なぜ彼らが世界クラスだと言えるのですか？"
      ],
      critiques: [
        "努力はしていますが、方向性が間違っています。あなたの技術スタックは非常に脆弱です。",
        "この分野は魅力的ですが、無限の資金を持つ巨人たちと戦うことになります。",
        "数字を把握していないということは、ビジネスを理解していないということです。目を覚ましなさい。"
      ],
      offers: {
        cash: "1.5億円",
        equity: 20,
        terms: "私のポートフォリオにある技術スタックと即座に統合すること。ロイヤリティなしで20%の株式。"
      },
      exit: "素晴らしい人柄ですが、技術的な防御力が足りません。今回は見送ります（OUT）。"
    },
    [InvestorId.BEATRICE]: {
      questions: [
        "技術のことはどうでもいいです。これまでの最大の失敗と、そこからどう立ち直ったかを教えてください。",
        "あなたにはハングリー精神がありますか？なぜ私が苦労して稼いだお金をあなたに託さなければならないのですか？",
        "ブランディングが信じられないほど退屈です。どうやって人々にこのサービスを本気で気に留めてもらうのですか？",
        "共同創業者は誰ですか？なぜその人と上手くやっていけるのですか？",
        "現在、あなたが感じている最大の脆弱性について、直感は何と言っていますか？",
        "経営陣の中での意見の相違にはどのように対処していますか？",
        "最初に採用した人物と、その人を選んだ理由について教えてください。",
        "ユーザーを獲得するために行った、最も型破りなマーケティング手法は何ですか？",
        "もし明日会社が倒産したら、その次の日にあなたは何をしますか？",
        "この過酷な道のりを生き抜くための精神的な回復力（レジリエンス）があなたにあると思うのはなぜですか？"
      ],
      critiques: [
        "スマートすぎます。何にでも完璧に答える人は信用できません。",
        "私は馬ではなく、騎手に投資します。今のあなたは少し疲れているように見えます。",
        "あなたのエネルギーは好きですが、ビジネスモデルが砂上の楼閣のように感じられます。"
      ],
      offers: {
        cash: "1.5億円",
        equity: 15,
        terms: "マーケティングサイトの完全なリブランディングと、15%の株式を要求します。"
      },
      exit: "直感的にピンときません。私は自分の直感を信じる必要があります。今回は見送ります（OUT）。"
    },
    [InvestorId.LEONA]: {
      questions: [
        "Is this a hero or a zero? Can this be explained to a normal person in 5 seconds?",
        "What is your manufacturing cost vs. retail price? How do we scale the supply chain?",
        "Have you thought about retail distribution or QVC? This feels perfect mass market.",
        "What is your return rate? If customers don't love it, we have nothing.",
        "What is your packaging strategy? Does it pop on a crowded retail shelf?",
        "Do you have a utility patent or just a design patent on this product?",
        "有料広告なしで、オーガニックに何ユニット販売しましたか？",
        "繁忙期の在庫管理をどのように行う計画ですか？",
        "この製品は、他のアクセサリーと簡単にセット販売やアップセルができますか？",
        "これまでに受け取った顧客からの最大の不満（クレーム）は何ですか？"
      ],
      critiques: [
        "賢い製品ですが、ニッチすぎます。もっと大衆にアピールする必要があります。",
        "パッケージがひどいです。小売店の棚で目立つようにする必要があります。",
        "明日にも1万店舗に導入する手助けができますが、あなたはそのボリュームに対応する準備ができません。"
      ],
      offers: {
        cash: "1.5億円",
        equity: 18,
        terms: "18%の株式、およびすべての小売およびテレビショッピング流通の独占権。"
      },
      exit: "私の流通ネットワークを活用するには少し早すぎます。成功を祈りますが、今回は見送ります（OUT）。"
    }
  }
};

// Fun Banter Templates for Shark Disagreements
export const SHARK_BANTER = {
  [Language.EN]: {
    [InvestorId.VINCENT]: [
      "Oh please, Beatrice! Gut feelings don't pay dividends. Show me the cold hard cash!",
      "Leona, mass appeal is great, but if the margins are zero, 18% of zero is still zero!",
      "Marcus, your tech stack talk is fancy, but this valuation is a complete fantasy!"
    ],
    [InvestorId.MARCUS]: [
      "Vincent, you're being greedy again with those royalties. You're going to choke this baby in its crib!",
      "Beatrice, that's just emotional. This is a software scale play, not a neighborhood bakery!",
      "Leona, retail is nice, but this is an enterprise SaaS platform. It doesn't belong on TV!"
    ],
    [InvestorId.BEATRICE]: [
      "Vincent, you have no soul. This founder has the fire in their belly, and that's what matters!",
      "Marcus, you're overcomplicating it with your tech jargon. It's all about trust and branding!",
      "Leona, not everything needs to pop on a retail shelf. Some things are built on pure passion!"
    ],
    [InvestorId.LEONA]: [
      "Vincent, your royalty demands are going to kill their cash flow. Be fair for once!",
      "Marcus, tech is great, but if a normal person can't understand it in five seconds, it's a zero!",
      "Beatrice, trust is wonderful, but we need a real retail distribution strategy to survive!"
    ]
  },
  [Language.JA]: {
    [InvestorId.VINCENT]: [
      "おいおい、ベアトリス！直感なんて配当を支払っちゃくれないよ。冷酷なキャッシュを見せてくれ！",
      "レオナ、大衆受けは素晴らしいが、マージンがゼロなら、ゼロの18%はやっぱりゼロだ！",
      "マークス、君の技術スタックの話は立派だが、この評価額は完全なファンタジーだ！"
    ],
    [InvestorId.MARCUS]: [
      "ヴィンセント、またロイヤリティで強欲になってるな。このスタートアップをゆりかごの中で窒息させる気か！",
      "ベアトリス、それはただの感情論だ。これはソフトウェアのスケールプレイであって、近所のパン屋じゃない！",
      "レオナ、テレビショッピングはいいが、これはエンタープライズSaaSだ。テレビには向かないよ！"
    ],
    [InvestorId.BEATRICE]: [
      "ヴィンセント、あなたには血も涙もないわね。この創業者にはハングリー精神がある。それこそが重要なのよ！",
      "マークス、技術的な専門用語で難しく考えすぎよ。大切なのは信頼とブランディングよ！",
      "レオナ、すべての商品が小売店の棚で目立つ必要はないわ。情熱だけで作られるものもあるのよ！"
    ],
    [InvestorId.LEONA]: [
      "ヴィンセント、あなたのロイヤリティ要求は彼らのキャッシュフローを殺してしまうわ。一度くらい公平になりなさい！",
      "マークス、技術は素晴らしいけれど、普通の人が5秒で理解できなければ、それはゼロよ！",
      "ベアトリス、信頼は素晴らしいけれど、生き残るためには本物の小売流通戦略が必要よ！"
    ]
  }
};