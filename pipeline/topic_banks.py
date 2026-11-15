"""Topic banks ported verbatim from the n8n nodes 'Load Past Topics' and 'Pick Shape'."""

# Topics used before the history file existed (t = epoch milliseconds, n = niche, o = opening, l = lesson).
SEED = [
    {'t': 1794025800000, 'n': 'Life philosophy and existential reflections', 'o': 'old clock, wasting time pleasing people', 'l': 'stop living for the views of others, live for your own satisfaction'},
    {'t': 1794038400000, 'n': 'Love, relationships and realistic expectations', 'o': 'garden trees, mango gives no shade, neem no sweet fruit', 'l': 'no partner meets every need, accept the right partner with flaws instead of a perfect one'},
    {'t': 1794051000000, 'n': 'Human behavior, comparison and contentment', 'o': 'glass of water held too long', 'l': 'carrying the success of others in your mind exhausts you, choose your own peace over comparison'},
    {'t': 1794063600000, 'n': 'Moral stories and philosophical fables', 'o': 'two frogs at a pond, one jealous of the other', 'l': 'comparison and jealousy cost you the safe, content place you already had'},
    {'t': 1794112200000, 'n': 'Love, relationships and realistic expectations', 'o': 'two flowers growing together', 'l': 'your partner is a beautiful part of your world, not your whole world, accept their separate identity'},
]

WINDOW_DAYS = 21
TRUTH_SHARE = 0.6
PATTERN_SHARE = 0.5

# Story mode niches.
NICHES = [
    {'name': 'Relatives and family reality', 'w': 20,
     'brief': 'Relatable stories about relatives and extended family: what relatives really think versus what they say, people who burn at your success, praise in front and criticism behind, how poor or struggling relatives are treated, the eldest son burden, family pressure, and how relations change after marriage. Specific, believable family moments that viewers instantly recognise from their own home.',
     'themes': ['रिश्तेदारों की असली सोच', 'शादी के बाद रिश्तों का बदलना', 'सफल होने पर जलने वाले लोग', 'घर के बड़े बेटे की जिम्मेदारी', 'सामने तारीफ, पीछे बुराई', 'गरीब रिश्तेदारों के साथ व्यवहार', 'जब जेब खाली हो तब रिश्तों की पहचान', 'हर रिश्तेदार अपना नहीं होता'],
     'guide': 'Usual telling is a reality check about relatives. It often opens on a common experience or contradiction viewers instantly recognise, shows one concrete moment (a gathering, a wedding, a money problem, a comparison), lets the conflict come from a comment or a change in behaviour, shows how the person feels or responds, and lands the hidden reality as one memorable truth about relationships. It can just as well be told as a small emotional story with a character, or as a sharp observation with a contrast, whichever fits the idea best. One idea, one main emotion, specific and believable, never a lecture. Do not stretch a short idea; every sentence must add curiosity, emotion or meaning.'},
    {'name': 'Parents and emotional family stories', 'w': 10,
     'brief': 'Emotional, shareable stories about parents and children: a father silent sacrifice, a mother unfulfilled wishes, ageing parents who are lonely, why a son changes after growing up, respect for parents, and the dreams of a poor father. Sincere, never melodramatic, the kind a viewer sends to a parent or a sibling.',
     'themes': ['पिता की खामोश कुर्बानी', 'मां की अधूरी इच्छाएं', 'बुढ़ापे में अकेले माता-पिता', 'बेटा बड़ा होकर क्यों बदल जाता है', 'मां-बाप की इज्जत', 'गरीब पिता के सपने', 'बूढ़े माता-पिता की सबसे बड़ी जरूरत'],
     'guide': 'Usual telling is an emotional mini-story about sacrifice. It often opens with an emotional observation or a quiet moment, introduces one parent or child, shows an ordinary but meaningful sacrifice, anchors it in one small symbolic object or moment that you invent fresh for this story (something real families would have), lets the child understand it late, and closes with gratitude, respect or a quiet realization. Time passing, a reversal, or starting from the ending can work too. Keep it sincere and understated, never melodramatic, and let one detail carry the feeling instead of explaining it.'},
    {'name': 'Relationship truth and emotional stories', 'w': 25,
     'brief': 'Romance, heartbreak and emotional connection told as honest truths: real love versus show, when only one person keeps the relationship alive, why respect matters in love, how relationships change, betrayal and trust, and the real reasons distance grows between two people. Shareable with a partner or a friend.',
     'themes': ['सच्चा प्यार और दिखावा', 'जब एक इंसान ही रिश्ता निभाता है', 'प्यार में इज्जत क्यों जरूरी है', 'बदलते हुए रिश्ते', 'धोखा और भरोसा', 'दूरियां बढ़ने की असली वजह', 'शादी के बाद बदलती प्राथमिकताएं', 'पत्नी की इज्जत'],
     'guide': 'Usual telling is an emotional truth about a relationship. It often names a painful, familiar experience, shows what the relationship was like, what changed in attention, communication or behaviour, how one person keeps trying while the other drifts, and what finally becomes clear, ending on one meaningful thought. It can also be a pattern explained through observable behaviour, a conversation, or a different perspective on something people misread. Describe behaviour and feelings only, never diagnose anyone or label a personality or mental condition. Stay on one emotion; let the realization feel earned, not announced.'},
    {'name': 'Middle-class and society reality', 'w': 20,
     'brief': 'Social commentary and relatable observations about middle-class life: how money changes society, why the hard work of the poor gets no respect, a life of show-off, double standards of society, the pain of jobs and unemployment, and the gap between what people think and real life.',
     'themes': ['पैसे से बदलता समाज', 'गरीब की मेहनत की कोई कदर क्यों नहीं', 'दिखावे की जिंदगी', 'समाज के दोहरे मापदंड', 'नौकरी और बेरोजगारी का दर्द', 'लोगों की सोच और असली जिंदगी', 'आज का दिखावा और कल की परेशानी', 'उधार देने से पहले'],
     'guide': 'Usual telling is a social reality check. It often opens with an uncomfortable truth or a relatable pressure, shows a concrete everyday situation (salary, bills, fees, expectations), the impossible choices people face, the contrast between what others see and what happens privately, and then the larger observation, ending with an empathetic or thought-provoking line. It can also be one small scene or a comparison that makes the point without stating it. Be concrete, never invent statistics, and keep it empathetic rather than preachy or angry.'},
    {'name': 'Self-respect and life lessons', 'w': 8,
     'brief': 'Grounded motivation, not quote-style: stop pleasing everyone, know your worth, silence is not weakness, lessons from hard times, distance from wrong people, restarting after failure. Told through a specific situation, never as generic advice.',
     'themes': ['हर किसी को खुश करना बंद करो', 'अपनी कीमत पहचानो', 'चुप रहना कमजोरी नहीं', 'मुश्किल समय की सीख', 'गलत लोगों से दूरी', 'असफलता के बाद दोबारा शुरुआत', 'किसी को बार-बार अपनी अहमियत मत बताओ', 'जब इंसान अकेले रहना सीख जाता है'],
     'guide': 'Usual telling is a realization. It often opens with a challenging observation, names a common mistake people make, shows what it quietly costs them, marks the moment of understanding, and gives one specific, practical insight with a line worth remembering. It can also be a short scene or a hard-hitting truth followed by one small achievable step. Keep it grounded in a situation, never a list of slogans, and give the viewer one sharp insight, not five.'},
    {'name': 'Success, money and career reality', 'w': 7,
     'brief': 'Aspiration and practical motivation: the journey from poor to rich, the truth before success, habits of earning and saving, job versus business, value of time, and why people respect you only after you succeed. Honest and grounded, no get-rich-quick hype or invented numbers.',
     'themes': ['गरीब से अमीर बनने का सफर', 'सफलता से पहले की सच्चाई', 'पैसा कमाने और बचाने की आदतें', 'नौकरी बनाम बिजनेस', 'समय की कीमत', 'लोग सफलता के बाद ही सम्मान क्यों देते हैं', 'सफल इंसान की सबसे बड़ी गलती'],
     'guide': 'Usual telling is a struggle-to-growth story. It often challenges the usual idea of success, shows a goal, the obstacle (failure, rejection, money trouble, criticism), the decision or sacrifice, steady progress through discipline, and a realistic takeaway. It can also be the hidden side of someone visible success, or a contrast between what people see now and what it cost. Stay honest and grounded, no hype, no get-rich promises, no invented numbers.'},
]

# Emotional truth mode niches (60% of runs).
TRUTH_NICHES = [
    {'name': 'Love fights, naraazgi and manana', 'w': 28,
     'brief': 'The feelings inside love that everyone has lived but rarely says: fighting most with the person you love most, getting upset because you trust they will make it up, pretending not to care while secretly checking on them, small acts of caring that look like anger, and the comfort of the person you fight with.',
     'themes': ['जिससे सबसे ज्यादा प्यार उसी से सबसे ज्यादा लड़ाई', 'नाराज होना भी भरोसे की निशानी है', 'ब्लॉक करके भी चुपके से देखना', 'बेपरवाही का दिखावा, परवाह की सच्चाई', 'रूठना और मनाना', 'जिसके बिना रह नहीं सकते उसी से शिकायतें'],
     'guide': 'One feeling, said in the viewer own voice. Open on the feeling or on a belief everyone repeats, show it with one or two tiny everyday behaviours, then turn it gently to what it really means (fear of losing, trust, care), and end on a line that comforts or stings softly. No named characters, no plot.'},
    {'name': 'Expectations, one-sided effort and feeling unvalued', 'w': 24,
     'brief': 'Giving time, care and effort and hoping for a little understanding back; silent expectations; people who only come when they need something; being the one who always reaches out; the pain of not being noticed; giving your heart to a place that does not value it.',
     'themes': ['उम्मीद रखना गलत नहीं, गलत जगह रखना है', 'हमेशा एक ही इंसान कोशिश करता है', 'बिना कहे समझे जाने की चाह', 'जो सिर्फ जरूरत में याद करे', 'बिना मांगे थोड़ी सी कोशिश', 'दिल लगाने की सही जगह'],
     'guide': 'One honest feeling and one gentle turn. A common belief is questioned, a few everyday proofs make the viewer nod, and the turn names what is really going on without blaming anyone. No named characters, no plot.'},
    {'name': 'Being an option: self-worth and self-respect in love', 'w': 22,
     'brief': 'The hard truth that you can be everything to someone who treats you as one option; why giving too much importance makes you lose your own; changing yourself so much for someone that you stop recognising yourself; knowing your worth without bitterness; staying where you are valued.',
     'themes': ['जिसे अपनी जरूरत समझा, उसके लिए आप सिर्फ एक ऑप्शन', 'किसी को इतनी अहमियत मत दो कि खुद की खो दो', 'किसी के लिए खुद को इतना मत बदलो', 'जहां कद्र नहीं वहां दिल मत लगाओ', 'जरूरत और आदत का फर्क', 'खुद को चुनना'],
     'guide': 'A truth that hurts a little and protects the viewer. It may build through a pattern of simple comparisons or through one clear contrast, then states the truth softly and returns the viewer to their own worth. Never bitter, never blaming a gender.'},
    {'name': 'Spiritual love and timeless symbols', 'w': 10,
     'brief': 'Widely known stories and symbols of love seen from a fresh angle: Radha and Krishna, Meera, the diya and the wind, the moon and the sea. Told as a gentle perspective (शायद), never as scripture fact and never disrespectful to any faith.',
     'themes': ['राधा-कृष्ण का नाराज होना और मनाना', 'सच्चे प्रेम की अलग पहचान', 'इंतजार का प्रेम', 'दीया और हवा', 'बिना पाए भी जुड़े रहना'],
     'guide': 'Start from the way people usually tell the story, then offer a perspective that flips it and ties it to everyday feelings. Phrase it as a perspective, not as scripture.'},
    {'name': 'Missing, silence, distance and moving on', 'w': 8,
     'brief': 'The quiet side of relationships: missing someone and not saying it, the silence after a fight, people who drift apart without a fight, learning to let go, and the strength of staying quiet.',
     'themes': ['याद आना पर बताना नहीं', 'लड़ाई के बाद की खामोशी', 'बिना झगड़े दूर हो जाना', 'छोड़ देना भी एक हिम्मत है', 'जो चले गए उनका सुकून'],
     'guide': 'One quiet feeling, a few tiny proofs, and a soft ending that gives the viewer peace instead of pain.'},
    {'name': 'Everyday truths through nature and simple comparisons', 'w': 8,
     'brief': 'Life and love truths told through simple natural pairs and familiar objects: air and breath, water and fish, soil and seed, light and moth, a river and its banks. A repeating structure that builds rhythm and ends on one human truth.',
     'themes': ['जिसे हमारी जरूरत नहीं, उसे हमारी कमी नहीं खलती', 'नदी और किनारे', 'पतंग और डोर', 'पेड़ और छाया', 'दिया और रोशनी'],
     'guide': 'Use a repeating structure of two or three pairs (this needs that, but that does not even notice), then turn it into the human truth. Pick fresh pairs each time.'},
]

# Pattern shape niches (half of the truth mode runs).
PATTERN_NICHES = [
    {'name': 'Ironies of life: if this then that', 'w': 30,
     'brief': 'Everyday ironies where a common belief does not deliver what it promises: age and wisdom, degrees and manners, money and peace, status and kindness, a crowd and real support, show and substance. The real cause is character, intention or effort. The irony aims at ideas and habits, never at a religion, community, profession or gender.',
     'themes': ['उम्र से अक्ल नहीं आती', 'डिग्री और तमीज का फर्क', 'पैसे से सुकून नहीं मिलता', 'भीड़ और अपनों का फर्क', 'बड़ा पद, छोटा दिल', 'दिखावे और असलियत का फर्क'],
     'guide': 'Pattern of if-then ironies, then the real cause in one plain line.'},
    {'name': 'Have and have-not: time, money and family', 'w': 26,
     'brief': 'Matching pairs of what one person has and another lacks, ending on a warm truth: money without time and time without money, the city dream and the home meal, a mother scolding and a mother missed, children busy and parents waiting, what is near and ignored versus what is gone and searched for.',
     'themes': ['जिसके पास पैसा उसके पास वक्त नहीं', 'शहर की कमाई और घर की रोटी', 'माँ की डांट और माँ की कमी', 'बच्चे व्यस्त और माँ-बाप इंतजार में', 'जो पास है उसकी कद्र नहीं', 'जब तक है तब तक कद्र करो'],
     'guide': 'Pattern of matching have and have-not pairs, then one warm direct line to the viewer. Sincere, never melodramatic.'},
    {'name': 'Gift and lack: nobody is perfect', 'w': 20,
     'brief': 'The world gave each thing one gift and held back another (a fruit, a flower, a river, a metal, the sun and the moon), so no person or relationship can be perfect. Choose fresh pairs each time and turn them into a gentle truth about expectations, partners, family or self.',
     'themes': ['हर चीज को कुदरत ने एक कमी दी है', 'चांद की ठंडक, सूरज की रोशनी', 'समंदर की गहराई, नदी की मिठास', 'कोई भी इंसान परफेक्ट नहीं होता', 'रिश्तों में परफेक्ट की तलाश', 'अधूरापन भी कुदरत का नियम है'],
     'guide': 'Pattern of five to seven gift-and-lack pairs, then the turn to the viewer own life.'},
    {'name': 'Quiz and twist: the costliest, heaviest, hardest things', 'w': 14,
     'brief': 'A short question about the most expensive, heaviest, cheapest, hardest or most precious thing in life, the answers everyone expects, then a real answer that surprises and a soft closing line. Short and quotable. Pick a fresh question and answer each time.',
     'themes': ['दुनिया की सबसे महंगी चीज क्या है', 'सबसे भारी चीज क्या है', 'सबसे सस्ती पर सबसे कीमती चीज', 'सबसे मुश्किल काम क्या है', 'सबसे बड़ा तोहफा क्या है'],
     'guide': 'Quiz and twist: question, expected answers, the real answer, a soft closing line. Short.'},
    {'name': 'What we realise too late', 'w': 10,
     'brief': 'Truths about valuing things only after they are gone or changed: yesterday, parents voices, a friend, health, a quiet home, simple moments. Told through parallel lines, never as a lecture, ending on a gentle push to value what is here today.',
     'themes': ['जो चला गया उसकी तलाश, जो पास है उसकी अनदेखी', 'आज जो शोर लगता है कल वही आवाज ढूंढोगे', 'समय रहते कह देना', 'बीता हुआ कल', 'आज की कद्र'],
     'guide': 'Parallel lines of before and after, then one gentle line that returns the viewer to today.'},
]
