# -*- coding: utf-8 -*-
import sqlite3
import datetime

news_items = [
    {
        'title': '全球彩票历史新纪录！美国“强力球”开出20.4亿美元天文巨奖',
        'image_url': 'https://images.unsplash.com/photo-1559526324-4b87b5e36e44?auto=format&fit=crop&w=800&q=80',
        'summary': '美国加利福尼亚州一位彩民独中强力球历史上最高奖池20.4亿美元（折合人民币逾140亿元），打破人类历史上单人中奖金额最高世界纪录。',
        'content': '''<p>近日，美国“强力球”（Powerball）彩票迎来了全球瞩目的历史性时刻。在历经连续40期无人命中头奖后，累积奖池一路飙升至创纪录的20.4亿美元（约合人民币145亿元）。据加利福尼亚州彩票官方机构公布，这张改写人类博彩历史的幸运彩票售出于洛杉矶郡阿尔塔迪纳的一家加油站便利店。</p>
<p>该巨奖不仅刷新了2016年三位彩民分享15.86亿美元的纪录，更一举创下了人类彩票史上由单张彩票独揽的最高金额历史纪录。中奖得主最终选择了一次性领取现金额度，扣税后依然获得了一笔改变人生的庞大财富。出售该中奖彩票的便利店店主也因此获得了100万美元的最高销售奖励。</p>
<p>彩票官员表示，强力球之所以能累积出如此庞大的奖池，得益于跨州销售的规模效应以及极其精密的概率结构。巨奖在全美范围内掀起了购彩狂潮，同时也为公共教育基金筹集了创纪录的专项公益资金。</p>''',
        'created_at': (datetime.datetime.now() - datetime.timedelta(days=1)).strftime('%Y-%m-%d %H:%M:%S'),
        'is_homepage_display': 1,
        'is_public': 1
    },
    {
        'title': '中国双色球史上最高奖！浙江绍兴彩民110倍投注独揽5.65亿元',
        'image_url': 'https://images.unsplash.com/photo-1518609878373-06d740f60d8b?auto=format&fit=crop&w=800&q=80',
        'summary': '中国福利彩票双色球开奖爆出震撼巨奖，浙江省新昌县一彩民凭借自选号码进行了110倍倍投，成功中得110注一等奖，总揽5.65亿元巨奖。',
        'content': '''<p>中国福利彩票双色球开奖在全国彩民的见证下诞生了中国彩市的神级纪录。来自浙江省绍兴市新昌县的一位幸运彩民，在当地福彩投注站以两张彩票对同一组号码各进行了110倍投注，精准击中当期开出的全部红球与蓝球，一举包揽110注一等奖，总奖金高达5.65亿元人民币。</p>
<p>这是中国福利彩票自发行以来诞生的最大单人单期中奖纪录。巨奖得主随后现身浙江省福彩中心完成验票兑奖，在领奖现场主动向慈善机构捐赠了2000万元用于社会公益事业与养老助残项目，成就了一段公益福彩与好运相辉映的佳话。</p>
<p>福彩专家指出，双色球的倍投机制在奖池充足的前提下为大奖突破亿元提供了可能，同时也再三提醒广大购彩者：彩票本质是公益事业与娱乐体验，倍投须量力而行，理性投注才是长久之道。</p>''',
        'created_at': (datetime.datetime.now() - datetime.timedelta(days=2)).strftime('%Y-%m-%d %H:%M:%S'),
        'is_homepage_display': 1,
        'is_public': 1
    },
    {
        'title': '欧洲百万触及封顶上限：2.4亿欧元无敌巨奖花落奥地利',
        'image_url': 'https://images.unsplash.com/photo-1514525253161-7a46d19cd819?auto=format&fit=crop&w=800&q=80',
        'summary': '欧洲跨国彩票“欧洲百万”在连续多期无人中出头奖后触发2.4亿欧元（约合人民币18.8亿元）的奖金硬顶，最终由奥地利一注单式票独得。',
        'content': '''<p>覆盖英国、法国、西班牙、奥地利等欧洲多国的“欧洲百万”（EuroMillions）超级奖池迎来了万众期待的封顶开奖。由于欧洲百万规则设有奖金上限机制，当头奖奖池达到2.4亿欧元（约合人民币18.8亿元）时不再增加，多余奖金将自动滚入二级奖池。在当晚激动人心的摇奖中，全部7个号码（5个基本号码+2个幸运星号码）被精准命中。</p>
<p>奥地利国家彩票管理机构证实，这位仅花费2.5欧元购买了单注电脑机选票的奥地利普通市民，成为了欧洲跨国彩票史上斩获最高单笔奖金的个人，创下了该国乃至整个欧洲博彩史上的新标杆。</p>
<p>奥地利彩票机构为中奖者提供了专业的匿名保护以及私人财富管理咨询团队，帮助中奖家庭平稳适应这一天文数字级别的财富跃迁。</p>''',
        'created_at': (datetime.datetime.now() - datetime.timedelta(days=3)).strftime('%Y-%m-%d %H:%M:%S'),
        'is_homepage_display': 1,
        'is_public': 1
    },
    {
        'title': '体彩超级大乐透震撼时刻：山东淄博彩民追加倍投独中4.97亿元',
        'image_url': 'https://images.unsplash.com/photo-1518133910546-b6c2fb7d79e3?auto=format&fit=crop&w=800&q=80',
        'summary': '国家体育彩票超级大乐透第14090期开奖，山东淄博一彩民以60倍单式追加投注击中头奖，总计收获4.97亿元奖金，刷新体彩历史最高纪录。',
        'content': '''<p>国家体育彩票超级大乐透开奖中，山东省淄博市一网点爆出体彩历史上的最高奖金纪录。中奖彩票是一张1注号码追加60倍的单式彩票，投注金额仅为180元。凭借“基本投注+追加投注”的复合收益，该彩民共摘得60注追加一等奖，总奖金达到惊人的4.97亿元人民币。</p>
<p>这是体彩超级大乐透自上市以来单人中奖最高纪录。得益于大乐透独特的“追加投注”机制，每一注一等奖都额外获得了高额追加奖金加成，充分展现了追加投注在大乐透玩法中的巨大威力。</p>
<p>体彩中心表示，大乐透彩票筹集的公益金被广泛用于全民健身设施建设、奥运争光计划及各项社会民生保障项目，让幸运与爱心同行。</p>''',
        'created_at': (datetime.datetime.now() - datetime.timedelta(days=4)).strftime('%Y-%m-%d %H:%M:%S'),
        'is_homepage_display': 1,
        'is_public': 1
    },
    {
        'title': '传承两百年的幸运盛宴！西班牙“大胖子”圣诞彩票总奖池突破26亿欧元',
        'image_url': 'https://images.unsplash.com/photo-1492684223066-81342ee5ff30?auto=format&fit=crop&w=800&q=80',
        'summary': '全球规模最大的年度彩票盛事——西班牙“大胖子”（El Gordo）圣诞彩票开奖，总奖金规模突破26亿欧元，全镇居民共享头奖狂欢。',
        'content': '''<p>始于1812年的西班牙圣诞彩票“大胖子”（El Gordo）是全球公认中奖覆盖面最广、总奖金规模最庞大的彩票节日。在每年的12月22日，马德里皇家歌剧院都会由圣伊尔德丰索学校的学生以传统歌唱形式唱出中奖号码，全国电视直播开奖全过程，总奖池超过26亿欧元。</p>
<p>与强调单人独揽几亿美元的玩法不同，“大胖子”彩票采用按系列成套销售的模式，亲朋好友、甚至整个村庄和小镇居民往往共同集资购买同一个号码组合。头奖开出后，常有一个沿海小镇或小工厂的工人全员分享数千万乃至上亿欧元巨额奖金，成为一年一度全民欢腾的暖心狂欢。</p>
<p>这一传统不仅是西班牙人迎接新年的重要仪式，更是亲朋好友之间增进感情、寄托新年美好祝福的文化纽带。</p>''',
        'created_at': (datetime.datetime.now() - datetime.timedelta(days=5)).strftime('%Y-%m-%d %H:%M:%S'),
        'is_homepage_display': 1,
        'is_public': 1
    },
    {
        'title': '福彩快乐8上演概率奇迹：独特基诺算法与多倍投注引发现象级关注',
        'image_url': 'https://images.unsplash.com/photo-1579621970563-ebec7560ff3e?auto=format&fit=crop&w=800&q=80',
        'summary': '福彩快乐8游戏全国大奖频频爆出，作为每天开奖、80选20的创新型基诺玩法，快乐8凭借“选十中十”最高单注500万及选七等独特规则受到广泛关注。',
        'content': '''<p>中国福利彩票新锐主力玩法“快乐8”自全国推广以来，凭借其“天天开奖、返奖率高达58%、80选20”的独特基诺型数学模型，吸引了海量彩民关注。快乐8包含选一至选十等多种玩法，其中选十玩法只要全部命中20个开奖号码中的10个，即可命中单注最高500万元封顶奖金，且即便全不中也有奖金回报。</p>
<p>在近年来的开奖中，多次出现彩民利用多倍投注精准斩获数千万元乃至更高奖金的案例。概率专家提醒：快乐8玩法丰富多变，既可利用智能选号算法过滤冷热温码，也必须始终秉持理性购彩、量力而行的健康心态。</p>
<p>随着数字化分析工具的发展，越来越多的彩民开始运用统计学工具研究冷热出号规律，使得快乐8成为了技术型选号彩民的热门研究对象。</p>''',
        'created_at': (datetime.datetime.now() - datetime.timedelta(days=6)).strftime('%Y-%m-%d %H:%M:%S'),
        'is_homepage_display': 1,
        'is_public': 1
    }
]

db_paths = [
    r'd:\Projects\iShoot8\instance\ishoot.db',
    r'S:\iShoot\instance\ishoot.db',
    r'S:\iShootNew\instance\ishoot.db'
]

for p in db_paths:
    try:
        conn = sqlite3.connect(p)
        cur = conn.cursor()
        # 清除已有标题相同的旧数据，防止重复
        titles = [item['title'] for item in news_items]
        placeholders = ', '.join(['?'] * len(titles))
        cur.execute(f'DELETE FROM news WHERE title IN ({placeholders})', titles)
        
        for item in news_items:
            cur.execute('''INSERT INTO news (title, image_url, summary, content, created_at, updated_at, is_homepage_display, is_public)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                        (item['title'], item['image_url'], item['summary'], item['content'], item['created_at'], item['created_at'], item['is_homepage_display'], item['is_public']))
        conn.commit()
        cur.execute('SELECT COUNT(*) FROM news')
        count = cur.fetchone()[0]
        conn.close()
        print(f'Successfully updated {p}, total news count: {count}')
    except Exception as e:
        print(f'Error updating {p}: {e}')

