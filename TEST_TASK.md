AI Agent orqali Yuk Tashish Zaproslarini Avtomatik Matching Tizimi
Maqsad
Tizim yuk tashish sohasida avtomatik ravishda yaratiladigan zaproslar uchun mos transport vositalarini AI agent yordamida tavsiya qilishni ta'minlaydi. Agentning asosiy vazifasi yuk ortish joyiga eng yaqin yoki shu hududda turgan mashinalarni aniqlab, zapros yaratilgan zahoti tavsiya berishdir.
Asosiy Talablar
1. Zaproslar Jadvali (zaproslar)
Birinchi migration zaproslar nomli jadval yaratadi.
Ustunlar:
id
yuk_ortish_joyi
yuk_tushirish_joyi
yuklash_sanasi
created_at
updated_at
Biznes Logika:
Tizim avtomatik ravishda zaproslar yaratadi.
Har bir zapros 1 daqiqadan 10 daqiqagacha bo'lgan intervalda generatsiya qilinadi.
Kunlik yaratiladigan zaproslar soni kamida 400 ta bo'lishi kerak.
2. Malumotlar Jadvali (malumotlar)
Ikkinchi migration malumotlar nomli jadval yaratadi.
Ustunlar:
id
mashina_raqami
joriy_lokatsiya
created_at
updated_at
Vazifasi:
Ushbu jadval transport vositalari haqidagi ma'lumotlarni saqlaydi:
Mashina davlat raqami
Hozirgi joylashuvi (viloyat, shahar yoki GPS koordinata)
3. Agent Takliflari Logi (agent_takliflari)
Uchinchi migration agent_takliflari nomli jadval yaratadi.
Ustunlar:
id
zapros_id (FK -> zaproslar.id)
mashina_id (FK -> malumotlar.id)
zapros_yaratilgan_vaqti
agent_taklif_bergan_vaqti
created_at
updated_at
Vazifasi:
Agent ishlash samaradorligini monitoring qilish uchun:
Zapros qachon yaratilganini
Agent qachon tavsiya berganini
Qaysi mashina tavsiya qilinganini
saqlaydi.
AI Agent Vazifasi
Yangi zapros yaratilishini kuzatadi.
Zaprosdagi yuk_ortish_joyi ni aniqlaydi.
malumotlar jadvalidan shu hududda yoki eng yaqin joyda turgan mashinalarni qidiradi.
Eng mos mashinalarni reytinglaydi.
Tavsiya natijasini agent_takliflari jadvaliga yozadi.
Zapros yaratilgan va tavsiya berilgan vaqtlar orasidagi kechikish (latency) monitoring qilinadi.
Kutilayotgan Natija
Kuniga 400+ zapros avtomatik yaratiladi.
Har bir zapros uchun AI agent mos transport vositalarini avtomatik tavsiya qiladi.
Tavsiya berish vaqti log qilinadi.
Kelajakda agent samaradorligi va matching aniqligi bo'yicha analitika olish imkoniyati yaratiladi.


Vacancy

Компания: EGS GROUP

Должность: AI Engineer

Локация: Tashkent City, Nest One E-block, Ташкент

Требования:
• Опыт работы AI/ML Engineer от 2 лет.
• Опыт разработки RAG-систем и мультиагентных AI-сервисов.
• Уверенное владение PyTorch и TensorFlow.
• Опыт обучения, дообучения и развертывания AI/ML-моделей в production-среде.

Обязанности:
• Разработка и внедрение AI-решений в сфере логистики.
• Работа с ML/DL и Generative AI моделями.
• Обучение и дообучение моделей.
• Подбор ML/AI-алгоритмов под бизнес-задачи.
• Предобработка и анализ данных.