.pragma library

// Order within each entry: French, Dutch, Irish, Simplified Chinese,
// Traditional Chinese. Custom translations are pending human review.
var translations = {
    "Aphrodite OS installation": ["Installation de Aphrodite OS", "Aphrodite OS installeren", "Suiteáil Aphrodite OS", "安装 Aphrodite OS", "安裝 Aphrodite OS"],
    "Additional Packages": ["Logiciels supplémentaires", "Aanvullende pakketten", "Pacáistí breise", "附加软件包", "附加套件"],
    "Choose optional software and features to include in your installation.": ["Choisissez les logiciels et fonctions à ajouter.", "Kies de software en functies voor uw installatie.", "Roghnaigh na bogearraí agus gnéithe roghnacha le suiteáil.", "选择要安装的可选软件和功能。", "選擇要安裝的選用軟體和功能。"],
    "Gaming Optimizations": ["Optimisations pour les jeux", "Optimalisaties voor games", "Optamuithe cluichíochta", "游戏优化", "遊戲最佳化"],
    "Install Steam, Proton support, Vulkan libraries and performance utilities.": ["Installe Steam, la prise en charge de Proton, les bibliothèques Vulkan et des outils de performance.", "Installeert Steam, Proton-ondersteuning, Vulkan-bibliotheken en prestatiehulpmiddelen.", "Suiteáil Steam, tacaíocht Proton, leabharlanna Vulkan agus uirlisí feidhmíochta.", "安装 Steam、Proton 支持、Vulkan 库和性能工具。", "安裝 Steam、Proton 支援、Vulkan 程式庫和效能工具。"],
    "Gaming Mode": ["Mode jeu", "Gamemodus", "Mód Cluichíochta", "游戏模式", "遊戲模式"],
    "No Gaming Mode": ["Aucun mode jeu", "Geen gamemodus", "Gan Mhód Cluichíochta", "不使用游戏模式", "停用遊戲模式"],
    "Use Plasma with standard desktop gaming.": ["Jouez depuis le bureau Plasma.", "Speel games vanaf het Plasma-bureaublad.", "Úsáid Plasma chun cluichí a imirt ar an deasc.", "在 Plasma 桌面上运行游戏。", "在 Plasma 桌面上執行遊戲。"],
    "Desktop First (Recommended)": ["Bureau en premier (recommandé)", "Bureaublad eerst (aanbevolen)", "Deasc ar dtús (molta)", "桌面优先（推荐）", "桌面優先（建議）"],
    "Start in Plasma and switch to the dedicated Gamescope session from the login screen.": ["Démarrez dans Plasma et passez à la session Gamescope depuis l’écran de connexion.", "Start in Plasma en kies de Gamescope-sessie op het aanmeldscherm.", "Tosaigh in Plasma agus roghnaigh seisiún Gamescope ar an scáileán logála isteach.", "默认进入 Plasma，并可在登录界面切换到专用 Gamescope 会话。", "預設進入 Plasma，並可在登入畫面切換至專用 Gamescope 工作階段。"],
    "Gaming Mode First": ["Mode jeu en premier", "Gamemodus eerst", "Mód Cluichíochta ar dtús", "游戏模式优先", "遊戲模式優先"],
    "Prefer the dedicated Gamescope session at login. A password is still required.": ["Présélectionne la session Gamescope. Le mot de passe reste obligatoire.", "Selecteer de Gamescope-sessie vooraf. Een wachtwoord blijft vereist.", "Réamhroghnaigh seisiún Gamescope. Tá pasfhocal riachtanach fós.", "在登录界面预选 Gamescope 会话，仍需输入密码。", "在登入畫面預選 Gamescope 工作階段，仍需輸入密碼。"],
    "DaVinci Resolve Support": ["Prise en charge de DaVinci Resolve", "Ondersteuning voor DaVinci Resolve", "Tacaíocht do DaVinci Resolve", "DaVinci Resolve 支持", "DaVinci Resolve 支援"],
    "Install compatible graphics compute and multimedia dependencies. Obtain DaVinci Resolve separately from Blackmagic Design.": ["Installe les dépendances graphiques et multimédias compatibles. Téléchargez DaVinci Resolve séparément auprès de Blackmagic Design.", "Installeert compatibele grafische en multimedia-afhankelijkheden. Download DaVinci Resolve afzonderlijk bij Blackmagic Design.", "Suiteáil spleáchais chomhoiriúnacha ríomha GPU agus ilmheán. Faigh DaVinci Resolve ar leith ó Blackmagic Design.", "安装兼容的 GPU 计算和多媒体依赖项。请向 Blackmagic Design 单独获取 DaVinci Resolve。", "安裝相容的 GPU 運算及多媒體相依套件。請向 Blackmagic Design 另行取得 DaVinci Resolve。"],
    "Selected profiles require internet access. The base system installs offline. If a profile fails, check the installation details.": ["Les profils choisis nécessitent Internet. Le système de base s’installe hors ligne. En cas d’échec, consultez les détails de l’installation.", "Geselecteerde profielen vereisen internet. Het basissysteem wordt offline geïnstalleerd. Bekijk bij problemen de installatiedetails.", "Teastaíonn idirlíon do na próifílí roghnaithe. Suiteálfar an bunchóras as líne. Má theipeann ar phróifíl, seiceáil sonraí na suiteála.", "所选配置需要联网。基本系统可离线安装。若配置失败，请查看安装详情。", "所選設定檔需要網路。基本系統可離線安裝。若設定檔失敗，請查看安裝詳細資料。"],
    "Date and Time": ["Date et heure", "Datum en tijd", "Dáta agus am", "日期和时间", "日期和時間"],
    "Storage Configuration": ["Configuration du stockage", "Opslag configureren", "Cumraíocht stórála", "配置存储", "設定儲存空間"],
    "Software Installation": ["Installation des logiciels", "Software installeren", "Suiteáil bogearraí", "安装软件", "安裝軟體"],
    "System Configuration": ["Configuration du système", "Systeem configureren", "Cumraíocht córais", "配置系统", "設定系統"],
    "Finalization": ["Finalisation", "Afronden", "Críochnú", "正在收尾", "正在完成"],
    "Welcome": ["Bienvenue", "Welkom", "Fáilte", "欢迎", "歡迎"],
    "Installation and Storage": ["Installation et stockage", "Installatie en opslag", "Suiteáil agus stóráil", "安装和存储", "安裝和儲存"],
    "Create Account": ["Créer un compte", "Account aanmaken", "Cruthaigh cuntas", "创建账户", "建立帳號"],
    "Review and Install": ["Vérifier et installer", "Controleren en installeren", "Athbhreithnigh agus suiteáil", "检查并安装", "檢查並安裝"],
    "Automatically set date and time using time servers": ["Régler automatiquement la date et l’heure via des serveurs de temps", "Datum en tijd automatisch instellen via tijdservers", "Socraigh an dáta agus an t-am go huathoibríoch le freastalaithe ama", "使用时间服务器自动设置日期和时间", "使用時間伺服器自動設定日期和時間"],
    "Show AM/PM in the clock preview": ["Afficher AM/PM dans l’aperçu", "AM/PM weergeven in de klokweergave", "Taispeáin AM/PM sa réamhamharc", "在时钟预览中显示上午和下午", "在時鐘預覽中顯示上午和下午"],
    "NTP servers (optional, separated by spaces)": ["Serveurs NTP (facultatif, séparés par des espaces)", "NTP-servers (optioneel, gescheiden door spaties)", "Freastalaithe NTP (roghnach, scartha le spásanna)", "NTP 服务器（可选，以空格分隔）", "NTP 伺服器（選用，以空格分隔）"],
    "NTP servers": ["Serveurs NTP", "NTP-servers", "Freastalaithe NTP", "NTP 服务器", "NTP 伺服器"],
    "Year": ["Année", "Jaar", "Bliain", "年", "年"],
    "Month": ["Mois", "Maand", "Mí", "月", "月"],
    "Day": ["Jour", "Dag", "Lá", "日", "日"],
    "Hour (24-hour)": ["Heure (format 24 h)", "Uur (24-uursnotatie)", "Uair (clog 24 uair)", "小时（24 小时制）", "小時（24 小時制）"],
    "Minute": ["Minute", "Minuut", "Nóiméad", "分钟", "分鐘"],
    "Choose the timezone on the next page. Automatic time requires network access. Manual time is set when installation starts configuring the system.": ["Choisissez le fuseau horaire à la page suivante. Le réglage automatique nécessite le réseau. L’heure manuelle est appliquée lors de la configuration du système.", "Kies de tijdzone op de volgende pagina. Automatische tijd vereist een netwerk. De handmatige tijd wordt tijdens de systeemconfiguratie ingesteld.", "Roghnaigh an crios ama ar an gcéad leathanach eile. Teastaíonn líonra don am uathoibríoch. Socraítear an t-am láimhe le linn chumrú an chórais.", "请在下一页选择时区。自动校时需要网络。手动时间将在配置系统时设置。", "請在下一頁選擇時區。自動校時需要網路。手動時間將在設定系統時套用。"],
    "Installation Complete": ["Installation terminée", "Installatie voltooid", "Suiteáil críochnaithe", "安装完成", "安裝完成"],
    "Your operating system has been installed successfully.": ["Votre système d’exploitation a été installé.", "Uw besturingssysteem is geïnstalleerd.", "Suiteáladh do chóras oibriúcháin go rathúil.", "操作系统已成功安装。", "作業系統已成功安裝。"],
    "Remove the installation medium when prompted during restart.": ["Retirez le support d’installation lorsque vous y êtes invité au redémarrage.", "Verwijder het installatiemedium wanneer daarom wordt gevraagd.", "Bain an meán suiteála nuair a iarrtar é le linn atosaithe.", "重启时，请按提示移除安装介质。", "重新啟動時，請依提示移除安裝媒體。"],
    "Restart Now": ["Redémarrer maintenant", "Nu opnieuw opstarten", "Atosaigh anois", "立即重启", "立即重新啟動"],
    "Continue Using Live Environment": ["Continuer dans l’environnement live", "Live-omgeving blijven gebruiken", "Lean ar aghaidh sa timpeallacht bheo", "继续使用试用环境", "繼續使用試用環境"],
    "Optional package results": ["Résultats des logiciels facultatifs", "Resultaten voor optionele pakketten", "Torthaí na bpacáistí roghnacha", "可选软件包安装结果", "選用套件安裝結果"],
    "Installing": ["Installation en cours", "Installeren", "Suiteáil ar siúl", "正在安装", "正在安裝"]
}

function text(source, locale) {
    const key = locale.replace("-", "_");
    const language = key.split("_")[0];
    const index = ({fr: 0, nl: 1, ga: 2, zh_CN: 3, zh_TW: 4})[key]
        ?? ({fr: 0, nl: 1, ga: 2, zh: 3})[language];
    const entry = translations[source];
    return entry && index !== undefined ? entry[index] : source;
}
