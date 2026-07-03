require('dotenv').config();
const { Telegraf, Markup } = require('telegraf');

const BOT_TOKEN = process.env.BOT_TOKEN;
const COBALT_API_URL = process.env.COBALT_API_URL; // masalan: https://sizning-cobalt.up.railway.app

if (!BOT_TOKEN) {
  console.error('XATO: BOT_TOKEN muhit o\'zgaruvchisi topilmadi (.env fayliga qarang)');
  process.exit(1);
}
if (!COBALT_API_URL) {
  console.error('XATO: COBALT_API_URL muhit o\'zgaruvchisi topilmadi (.env fayliga qarang)');
  process.exit(1);
}

const bot = new Telegraf(BOT_TOKEN);

// Foydalanuvchi yuborgan linklarni vaqtincha saqlash uchun (Telegram callback_data 64 baytdan oshmasligi kerak, shu uchun to'liq URL emas, qisqa ID saqlaymiz)
const linkStore = new Map();
let counter = 0;

const URL_REGEX = /(https?:\/\/[^\s]+)/i;
const SUPPORTED = /(youtube\.com|youtu\.be|facebook\.com|fb\.watch|instagram\.com|tiktok\.com|x\.com|twitter\.com)/i;

bot.start((ctx) =>
  ctx.reply(
    "Salom! 👋\n\nMenga YouTube, Instagram, TikTok, Facebook yoki X (Twitter) havolasini yuboring — video (turli sifatlarda) yoki audio (MP3) ko'rinishida yuklab beraman."
  )
);

bot.on('text', async (ctx) => {
  const text = ctx.message.text;
  const match = text.match(URL_REGEX);
  if (!match) return; // oddiy matn bo'lsa, e'tiborsiz qoldiramiz

  const url = match[1];
  if (!SUPPORTED.test(url)) {
    return ctx.reply(
      "Bu havolani qo'llab-quvvatlamayman. YouTube, Instagram, TikTok, Facebook yoki X (Twitter) havolasini yuboring."
    );
  }

  const id = String(counter++);
  linkStore.set(id, url);
  // 15 daqiqadan keyin xotiradan tozalaymiz
  setTimeout(() => linkStore.delete(id), 15 * 60 * 1000);

  await ctx.reply(
    'Qaysi formatda yuklab olay?',
    Markup.inlineKeyboard([
      [
        Markup.button.callback('360p', `v_360_${id}`),
        Markup.button.callback('480p', `v_480_${id}`),
        Markup.button.callback('720p', `v_720_${id}`),
      ],
      [
        Markup.button.callback('1080p', `v_1080_${id}`),
        Markup.button.callback('Eng yaxshi sifat', `v_max_${id}`),
      ],
      [Markup.button.callback('🎵 Audio (MP3)', `a_mp3_${id}`)],
    ])
  );
});

bot.on('callback_query', async (ctx) => {
  const data = ctx.callbackQuery.data;
  const [kind, quality, id] = data.split('_');
  const url = linkStore.get(id);

  if (!url) {
    return ctx.answerCbQuery("Havola muddati tugadi, iltimos linkni qaytadan yuboring.", {
      show_alert: true,
    });
  }

  await ctx.answerCbQuery("Boshlandi, biroz kuting... ⏳");
  const waitMsg = await ctx.reply('⏳ Yuklanmoqda, biroz kuting...');

  try {
    const body =
      kind === 'a'
        ? { url, downloadMode: 'audio', audioFormat: 'mp3' }
        : { url, downloadMode: 'auto', videoQuality: quality };

    const res = await fetch(COBALT_API_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
      body: JSON.stringify(body),
    });
    const result = await res.json();

    if (result.status === 'error') {
      throw new Error(result.error?.code || "noma'lum xato");
    }

    let fileUrl, filename;
    if (result.status === 'tunnel' || result.status === 'redirect') {
      fileUrl = result.url;
      filename = result.filename;
    } else if (result.status === 'local-processing') {
      fileUrl = result.tunnel[0];
      filename = result.output?.filename;
    } else if (result.status === 'picker' && result.picker?.length) {
      // Masalan, TikTok slaydshou - birinchi elementni yuboramiz
      fileUrl = result.picker[0].url;
      filename = 'fayl';
    }

    if (!fileUrl) throw new Error('fayl havolasi topilmadi');

    if (kind === 'a') {
      await ctx.replyWithAudio(fileUrl, filename ? { filename } : undefined);
    } else {
      await ctx.replyWithVideo(fileUrl, filename ? { filename } : undefined);
    }
  } catch (err) {
    console.error(err);
    await ctx.reply(
      "❌ Yuklab bo'lmadi. Fayl juda katta bo'lishi yoki xizmat vaqtincha ishlamayotgan bo'lishi mumkin.\nXato: " +
        err.message
    );
  } finally {
    ctx.deleteMessage(waitMsg.message_id).catch(() => {});
  }
});

bot.launch();
console.log('Bot ishga tushdi ✅');

process.once('SIGINT', () => bot.stop('SIGINT'));
process.once('SIGTERM', () => bot.stop('SIGTERM'));
