import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import requests
import time
import logging
import urllib.parse
from flask import Flask, request, abort

# تهيئة نظام التسجيل
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TOKEN = '8052936091:AAFzLTZ9EQJSWauG9DmGjH2cWzrRx8pOtks'
PIXABAY_API_KEY = '51444506-bffefcaf12816bd85a20222d1'
ADMIN_ID = 6689435577 # معرف المدير
WEBHOOK_URL = 'https://vixabot-3yzy.onrender.com/webhook'  # تأكد من تطابق هذا مع عنوان URL الخاص بك

app = Flask(__name__)
bot = telebot.TeleBot(TOKEN)

# قنوات الاشتراك الإجباري
REQUIRED_CHANNELS = ['@crazys7', '@AWU87']

# ذاكرة مؤقتة لتخزين نتائج البحث لكل مستخدم
user_data = {}
new_users = set()  # لتتبع المستخدمين الجدد

def is_valid_url(url):
    """التحقق من صحة عنوان URL"""
    try:
        result = urllib.parse.urlparse(url)
        return all([result.scheme, result.netloc])
    except:
        return False

def set_webhook():
    """تعيين ويب هوك للبوت"""
    try:
        bot.remove_webhook()
        time.sleep(1)
        bot.set_webhook(url=WEBHOOK_URL)
        logger.info("تم تعيين ويب هوك بنجاح")
    except Exception as e:
        logger.error(f"خطأ في تعيين ويب هوك: {e}")

@app.route('/webhook', methods=['POST'])
def webhook():
    """معالجة التحديثات الواردة من تلجرام"""
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return ''
    else:
        abort(403)

@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    # التحقق من المستخدم الجديد
    if user_id not in new_users:
        new_users.add(user_id)
        notify_admin(user_id, message.from_user.username)
    
    # التحقق من الاشتراك في القنوات
    not_subscribed = check_subscription(user_id)
    
    if not_subscribed:
        markup = InlineKeyboardMarkup()
        # إضافة أزرار للقنوات
        for channel in REQUIRED_CHANNELS:
            markup.add(InlineKeyboardButton(f"اشترك في {channel}", url=f"https://t.me/{channel[1:]}"))
        markup.add(InlineKeyboardButton("تحقق من الاشتراك", callback_data="check_subscription"))
        msg = bot.send_message(chat_id, "❗️ يجب الاشتراك في القنوات التالية أولاً:\n" + "\n".join([f"• {channel}" for channel in REQUIRED_CHANNELS]), reply_markup=markup)
        # حفظ معرف الرسالة الرئيسية للمستخدم
        if user_id not in user_data:
            user_data[user_id] = {}
        user_data[user_id]['main_message_id'] = msg.message_id
    else:
        show_main_menu(chat_id, user_id)

def notify_admin(user_id, username):
    """إرسال إشعار للمدير عند انضمام مستخدم جديد"""
    try:
        username = f"@{username}" if username else "بدون معرف"
        message = "مستخدم جديد انضم للبوت:\n\n"
        message += f"ID: {user_id}\n"
        message += f"Username: {username}"
        bot.send_message(ADMIN_ID, message)
    except Exception as e:
        logger.error(f"خطأ في إرسال إشعار للمدير: {e}")

def check_subscription(user_id):
    """التحقق من اشتراك المستخدم في جميع القنوات المطلوبة"""
    not_subscribed = []
    for channel in REQUIRED_CHANNELS:
        try:
            # الحصول على حالة المستخدم في القناة
            chat_member = bot.get_chat_member(chat_id=channel, user_id=user_id)
            if chat_member.status not in ['member', 'administrator', 'creator']:
                not_subscribed.append(channel)
        except Exception as e:
            logger.error(f"خطأ في التحقق من الاشتراك في {channel}: {e}")
            not_subscribed.append(channel)
    return not_subscribed

def show_main_menu(chat_id, user_id):
    # إعادة ضبط بيانات المستخدم
    if user_id not in user_data:
        user_data[user_id] = {}
    
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🔍 انقر للبحث", callback_data="search"))
    markup.add(InlineKeyboardButton("👤 عن المطور", callback_data="about_dev"))
    
    welcome_msg = "🎉 **مرحباً بك في PEXELBO**\n\n🔎 ابحث عن الصور والفيديوهات المجانية باللغة الإنجليزية"
    
    # إذا كانت هناك رسالة سابقة، نقوم بتعديلها بدلاً من إرسال رسالة جديدة
    if 'main_message_id' in user_data[user_id]:
        try:
            bot.edit_message_text(
                chat_id=chat_id,
                message_id=user_data[user_id]['main_message_id'],
                text=welcome_msg,
                reply_markup=markup,
                parse_mode='Markdown'
            )
            return
        except Exception as e:
            logger.error(f"خطأ في تعديل القائمة الرئيسية: {e}")
            # إذا فشل التعديل، نرسل رسالة جديدة
            msg = bot.send_message(chat_id, welcome_msg, reply_markup=markup, parse_mode='Markdown')
            user_data[user_id]['main_message_id'] = msg.message_id
    else:
        # إرسال رسالة جديدة
        msg = bot.send_message(chat_id, welcome_msg, reply_markup=markup, parse_mode='Markdown')
        user_data[user_id]['main_message_id'] = msg.message_id

@bot.callback_query_handler(func=lambda call: call.data == "check_subscription")
def verify_subscription(call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    not_subscribed = check_subscription(user_id)
    
    if not_subscribed:
        markup = InlineKeyboardMarkup()
        # إضافة أزرار للقنوات
        for channel in REQUIRED_CHANNELS:
            markup.add(InlineKeyboardButton(f"اشترك في {channel}", url=f"https://t.me/{channel[1:]}"))
        markup.add(InlineKeyboardButton("✅ تحقق من الاشتراك", callback_data="check_subscription"))
        
        try:
            bot.edit_message_text(
                chat_id=chat_id,
                message_id=call.message.message_id,
                text="❌ **لم تشترك بعد في القنوات التالية:**\n" + "\n".join([f"• {channel}" for channel in not_subscribed]),
                reply_markup=markup,
                parse_mode='Markdown'
            )
        except Exception as e:
            logger.error(f"خطأ في تعديل رسالة الاشتراك: {e}")
    else:
        bot.answer_callback_query(call.id, "✅ تم الاشتراك بنجاح! يمكنك الآن استخدام البوت.", show_alert=False)
        show_main_menu(chat_id, user_id)

@bot.callback_query_handler(func=lambda call: call.data == "search")
def show_content_types(call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    
    # التحقق من الاشتراك أولاً
    not_subscribed = check_subscription(user_id)
    if not_subscribed:
        bot.answer_callback_query(call.id, "❗️ يجب الاشتراك في القنوات أولاً", show_alert=True)
        return
    
    # إعادة ضبط بيانات البحث
    if user_id not in user_data:
        user_data[user_id] = {}
    
    # إخفاء الرسالة السابقة
    try:
        bot.answer_callback_query(call.id)
    except:
        pass
    
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("📷 Photos", callback_data="type_photo"))
    markup.add(InlineKeyboardButton("🔺 Vectors", callback_data="type_vector"))
    markup.add(InlineKeyboardButton("🎨 Illustrations", callback_data="type_illustration"))
    markup.add(InlineKeyboardButton("🎥 Videos", callback_data="type_video"))
    markup.add(InlineKeyboardButton("🌐 All", callback_data="type_all"))
    markup.add(InlineKeyboardButton("🔙 رجوع", callback_data="back_to_main"))
    
    try:
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=call.message.message_id,
            text="📂 **اختر نوع المحتوى:**",
            reply_markup=markup,
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"خطأ في عرض انواع المحتوى: {e}")

@bot.callback_query_handler(func=lambda call: call.data.startswith("type_"))
def request_search_term(call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    
    # التحقق من الاشتراك أولاً
    not_subscribed = check_subscription(user_id)
    if not_subscribed:
        bot.answer_callback_query(call.id, "❗️ يجب الاشتراك في القنوات أولاً", show_alert=True)
        return
    
    content_type = call.data.split("_")[1]
    
    # تخزين نوع المحتوى المختار
    if user_id not in user_data:
        user_data[user_id] = {}
    user_data[user_id]['content_type'] = content_type
    
    # طلب كلمة البحث مع زر إلغاء
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("❌ الغاء البحث", callback_data="cancel_search"))
    
    try:
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=call.message.message_id,
            text="🔍 **ارسل كلمة البحث باللغة الانجليزية:**",
            reply_markup=markup,
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"خطأ في طلب كلمة البحث: {e}")
    
    # حفظ معرف الرسالة للاستخدام لاحقاً
    user_data[user_id]['search_message_id'] = call.message.message_id
    # تسجيل الخطوة التالية
    bot.register_next_step_handler(call.message, process_search_term, user_id)

@bot.callback_query_handler(func=lambda call: call.data == "cancel_search")
def cancel_search(call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    show_main_menu(chat_id, user_id)

def process_search_term(message, user_id):
    chat_id = message.chat.id
    
    # التحقق من الاشتراك أولاً
    not_subscribed = check_subscription(user_id)
    if not_subscribed:
        show_subscription_required(chat_id, user_id)
        return
    
    search_term = message.text
    
    # حذف رسالة إدخال المستخدم
    try:
        bot.delete_message(chat_id, message.message_id)
    except Exception as e:
        logger.error(f"خطأ في حذف رسالة المستخدم: {e}")
    
    # استرجاع نوع المحتوى
    if user_id not in user_data or 'content_type' not in user_data[user_id]:
        show_main_menu(chat_id, user_id)
        return
    
    content_type = user_data[user_id]['content_type']
    
    # تحديث الرسالة السابقة لإظهار حالة التحميل
    try:
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=user_data[user_id]['search_message_id'],
            text="⏳ **جاري البحث في قاعدة البيانات...**",
            reply_markup=None,
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"خطأ في عرض رسالة التحميل: {e}")
    
    # البحث في Pixabay
    results = search_pixabay(search_term, content_type)
    
    if not results or 'hits' not in results or len(results['hits']) == 0:
        # عرض خيارات عند عدم وجود نتائج
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🔍 بحث جديد", callback_data="search"))
        markup.add(InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="back_to_main"))
        
        try:
            bot.edit_message_text(
                chat_id=chat_id,
                message_id=user_data[user_id]['search_message_id'],
                text=f"❌ **لم يتم العثور على نتائج لكلمة:** `{search_term}`\n\n⚠️ يرجى المحاولة بكلمات أخرى",
                reply_markup=markup,
                parse_mode='Markdown'
            )
        except Exception as e:
            logger.error(f"خطأ في عرض رسالة عدم وجود نتائج: {e}")
        return
    
    # حفظ النتائج
    user_data[user_id]['search_term'] = search_term
    user_data[user_id]['search_results'] = results['hits']
    user_data[user_id]['current_index'] = 0
    
    # عرض النتيجة الأولى في نفس رسالة "جاري البحث"
    show_result(chat_id, user_id, message_id=user_data[user_id]['search_message_id'])

def show_subscription_required(chat_id, user_id):
    """عرض رسالة طلب الاشتراك في القنوات"""
    markup = InlineKeyboardMarkup()
    for channel in REQUIRED_CHANNELS:
        markup.add(InlineKeyboardButton(f"اشترك في {channel}", url=f"https://t.me/{channel[1:]}"))
    markup.add(InlineKeyboardButton("✅ تحقق من الاشتراك", callback_data="check_subscription"))
    
    bot.send_message(chat_id, "❗️ **يجب الاشتراك في القنوات أولاً:**\n" + "\n".join([f"• {channel}" for channel in REQUIRED_CHANNELS]), reply_markup=markup, parse_mode='Markdown')

def search_pixabay(query, content_type):
    base_url = "https://pixabay.com/api/"
    params = {
        'key': PIXABAY_API_KEY,
        'q': query,
        'per_page': 50,
        'lang': 'en'
    }
    
    # تحديد نوع المحتوى
    if content_type == 'photo':
        params['image_type'] = 'photo'
    elif content_type == 'vector':
        params['image_type'] = 'vector'
    elif content_type == 'illustration':
        params['image_type'] = 'photo'
        params['category'] = 'design'
    elif content_type == 'video':
        params['video_type'] = 'all'
        base_url = "https://pixabay.com/api/videos/"
    else:  # all
        params['image_type'] = 'all'
    
    try:
        logger.info(f"البحث في Pixabay عن: {query} ({content_type})")
        response = requests.get(base_url, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()
        logger.info(f"تم العثور على {len(data.get('hits', []))} نتيجة")
        return data
    except Exception as e:
        logger.error(f"خطأ في واجهة Pixabay: {e}")
        return None

def show_result(chat_id, user_id, message_id=None):
    if user_id not in user_data or 'search_results' not in user_data[user_id]:
        try:
            bot.edit_message_text(
                chat_id=chat_id,
                message_id=user_data[user_id]['search_message_id'],
                text="⏰ **انتهت جلسة البحث، ابدأ بحثاً جديداً**",
                parse_mode='Markdown'
            )
        except:
            pass
        return
    
    results = user_data[user_id]['search_results']
    current_index = user_data[user_id]['current_index']
    search_term = user_data[user_id].get('search_term', '')
    
    if current_index < 0 or current_index >= len(results):
        try:
            bot.edit_message_text(
                chat_id=chat_id,
                message_id=user_data[user_id]['last_message_id'],
                text="🏁 **نهاية النتائج**",
                parse_mode='Markdown'
            )
        except:
            pass
        return
    
    item = results[current_index]
    
    # بناء الرسالة
    caption = f"🔍 **البحث:** {search_term}\n"
    caption += f"📊 **النتيجة {current_index+1} من {len(results)}**\n"
    if 'tags' in item:
        caption += f"🏷️ **الوسوم:** {item['tags']}\n"
    
    # بناء أزرار التنقل
    markup = InlineKeyboardMarkup()
    row_buttons = []
    if current_index > 0:
        row_buttons.append(InlineKeyboardButton("◀️ السابق", callback_data=f"nav_prev"))
    if current_index < len(results) - 1:
        row_buttons.append(InlineKeyboardButton("▶️ التالي", callback_data=f"nav_next"))
    
    if row_buttons:
        markup.row(*row_buttons)
    
    markup.add(InlineKeyboardButton("📥 تحميل", callback_data="download"))
    markup.add(InlineKeyboardButton("🔍 بحث جديد", callback_data="search"))
    markup.add(InlineKeyboardButton("🔙 الرئيسية", callback_data="back_to_main"))
    
    # إرسال النتيجة
    try:
        # إذا كانت النتيجة فيديو
        if 'videos' in item:
            video_url = item['videos']['medium']['url']
            
            # التحقق من صحة URL
            if not is_valid_url(video_url):
                raise ValueError("رابط الفيديو غير صالح")
            
            # محاولة تعديل الرسالة الحالية
            if message_id:
                try:
                    # تعديل الوسائط والتسمية التوضيحية معاً
                    bot.edit_message_media(
                        chat_id=chat_id,
                        message_id=message_id,
                        media=telebot.types.InputMediaVideo(
                            media=video_url,
                            caption=caption,
                            parse_mode='Markdown'
                        ),
                        reply_markup=markup
                    )
                    # حفظ معرف الرسالة
                    user_data[user_id]['last_message_id'] = message_id
                    return
                except Exception as e:
                    logger.error(f"فشل في تعديل رسالة الفيديو: {e}")
            
            # إرسال رسالة جديدة إذا لم تنجح عملية التعديل
            msg = bot.send_video(chat_id, video_url, caption=caption, reply_markup=markup, parse_mode='Markdown')
            user_data[user_id]['last_message_id'] = msg.message_id
        else:
            # الحصول على رابط الصورة
            image_url = item.get('largeImageURL', item.get('webformatURL', ''))
            
            # التحقق من صحة URL
            if not is_valid_url(image_url):
                raise ValueError("رابط الصورة غير صالح")
            
            # محاولة تعديل الرسالة الحالية
            if message_id:
                try:
                    # تعديل الوسائط والتسمية التوضيحية معاً
                    bot.edit_message_media(
                        chat_id=chat_id,
                        message_id=message_id,
                        media=telebot.types.InputMediaPhoto(
                            media=image_url,
                            caption=caption,
                            parse_mode='Markdown'
                        ),
                        reply_markup=markup
                    )
                    # حفظ معرف الرسالة
                    user_data[user_id]['last_message_id'] = message_id
                    return
                except Exception as e:
                    logger.error(f"فشل في تعديل رسالة الصورة: {e}")
            
            # إرسال رسالة جديدة إذا لم تنجح عملية التعديل
            msg = bot.send_photo(chat_id, image_url, caption=caption, reply_markup=markup, parse_mode='Markdown')
            user_data[user_id]['last_message_id'] = msg.message_id
    except Exception as e:
        logger.error(f"خطأ في عرض النتيجة: {e}")
        # المحاولة مع نتيجة أخرى
        user_data[user_id]['current_index'] += 1
        if user_data[user_id]['current_index'] < len(results):
            show_result(chat_id, user_id, message_id)
        else:
            show_no_results(chat_id, user_id)

def show_no_results(chat_id, user_id):
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🔍 بحث جديد", callback_data="search"))
    markup.add(InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="back_to_main"))
    try:
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=user_data[user_id]['search_message_id'],
            text="❌ **لم يتم العثور على أي نتائج**\n\n⚠️ يرجى المحاولة بكلمات أخرى",
            reply_markup=markup,
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"خطأ في عرض رسالة عدم وجود نتائج: {e}")

@bot.callback_query_handler(func=lambda call: call.data.startswith("nav_"))
def navigate_results(call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    action = call.data.split("_")[1]
    
    # التحقق من الاشتراك أولاً
    not_subscribed = check_subscription(user_id)
    if not_subscribed:
        bot.answer_callback_query(call.id, "❗️ يجب الاشتراك في القنوات أولاً", show_alert=True)
        return
    
    if user_id not in user_data or 'search_results' not in user_data[user_id]:
        bot.answer_callback_query(call.id, "⏰ انتهت جلسة البحث، ابدأ بحثاً جديداً")
        return
    
    # تحديث الفهرس
    if action == 'prev':
        user_data[user_id]['current_index'] -= 1
    elif action == 'next':
        user_data[user_id]['current_index'] += 1
    
    # حفظ معرف الرسالة الحالية (التي نضغط عليها)
    user_data[user_id]['last_message_id'] = call.message.message_id
    
    # عرض النتيجة الجديدة في نفس الرسالة
    show_result(chat_id, user_id, message_id=call.message.message_id)

@bot.callback_query_handler(func=lambda call: call.data == "download")
def download_content(call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    
    # التحقق من الاشتراك أولاً
    not_subscribed = check_subscription(user_id)
    if not_subscribed:
        bot.answer_callback_query(call.id, "❗️ يجب الاشتراك في القنوات أولاً", show_alert=True)
        return
    
    # إزالة أزرار التنقل
    try:
        bot.edit_message_reply_markup(
            chat_id=chat_id,
            message_id=call.message.message_id,
            reply_markup=None
        )
    except Exception as e:
        logger.error(f"خطأ في ازالة الازرار: {e}")
    
    # إظهار رسالة تأكيد
    bot.answer_callback_query(call.id, "✅ تم التحميل بنجاح!", show_alert=False)
    
    # إظهار خيارات جديدة في رسالة منفصلة
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🔍 بحث جديد", callback_data="search"))
    markup.add(InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="back_to_main"))
    
    bot.send_message(chat_id, "✅ **تم تحميل المحتوى بنجاح!**\n\nماذا تريد أن تفعل الآن؟", reply_markup=markup, parse_mode='Markdown')

@bot.callback_query_handler(func=lambda call: call.data == "about_dev")
def show_dev_info(call):
    dev_info = """
👤 **عن المطور** @Ili8_8ill

مطور مبتدئ في عالم بوتات تيليجرام، بدأ رحلته بشغف كبير لتعلم البرمجة وصناعة أدوات ذكية تساعد المستخدمين وتضيف قيمة للمجتمعات الرقمية. يسعى لتطوير مهاراته يومًا بعد يوم من خلال التجربة، التعلم، والمشاركة في مشاريع بسيطة لكنها فعالة.

**ما يميزه في هذه المرحلة:**
- حب الاستكشاف والتعلم الذاتي
- بناء بوتات بسيطة بمهام محددة
- استخدام أدوات مثل BotFather و Python
- الانفتاح على النقد والتطوير المستمر

**القنوات المرتبطة:**
@crazys7 - @AWU87

**رؤية المطور:**
الانطلاق من الأساسيات نحو الاحتراف، خطوة بخطوة، مع طموح لصناعة بوتات تلبي احتياجات حقيقية وتحدث فرقًا.

**للتواصل:**
تابع الحساب @Ili8_8ill
    """
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🔙 رجوع", callback_data="back_to_main"))
    
    try:
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=dev_info,
            reply_markup=markup,
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"خطأ في عرض معلومات المطور: {e}")

@bot.callback_query_handler(func=lambda call: call.data == "back_to_main")
def return_to_main(call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    show_main_menu(chat_id, user_id)

if __name__ == '__main__':
    logger.info("بدء تشغيل البوت...")
    set_webhook()
    app.run(host='0.0.0.0', port=10000)
