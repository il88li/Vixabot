import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import requests
import time
import logging
import urllib.parse
from flask import Flask, request, abort
import random
import threading
import schedule
from datetime import datetime, timedelta

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
REQUIRED_CHANNELS = ['@GRABOT7', '@iIl337']

# ذاكرة مؤقتة لتخزين نتائج البحث لكل مستخدم
user_data = {}
new_users = set()  # لتتبع المستخدمين الجدد

# قائمة الرموز التعبيرية المتحركة
ANIMATED_EMOJIS = ['🌿', '🌳', '🥝', '🍹', '👋', '🍻', '🥀', '🍒', '🍀', '🌻', '🌾', '🌴', '🍍', '🍇', '🍈', '🍉', '🍓', '🍅', '🍎', '🫚', '🥦', '🥬', '🥙', '🥗', '🧆', '🍯', '🧃']

# إحصائيات البوت
bot_stats = {
    'total_searches': 0,
    'total_users': 0,
    'active_sessions': 0,
    'last_activity': datetime.now()
}

def get_random_emoji():
    """إرجاع رمز تعبيري عشوائي"""
    return random.choice(ANIMATED_EMOJIS)

def update_bot_stats(activity_type="general"):
    """تحديث إحصائيات البوت"""
    bot_stats['last_activity'] = datetime.now()
    
    if activity_type == "search":
        bot_stats['total_searches'] += 1
    elif activity_type == "user":
        bot_stats['total_users'] = len(new_users)
    
    # تحديث عدد الجلسات النشطة
    active_sessions = 0
    for user_id, data in user_data.items():
        if 'last_interaction' in data:
            # إذا كان التفاعل خلال آخر 10 دقائق
            if datetime.now() - data['last_interaction'] < timedelta(minutes=10):
                active_sessions += 1
    bot_stats['active_sessions'] = active_sessions

def periodic_maintenance():
    """وظيفة الصيانة الدورية للبوت"""
    try:
        logger.info(f"{get_random_emoji()} بدء الصيانة الدورية للبوت")
        
        # تحديث إحصائيات البوت
        update_bot_stats()
        
        # تنظيف البيانات القديمة (أكثر من ساعة)
        current_time = datetime.now()
        users_to_remove = []
        for user_id, data in user_data.items():
            if 'last_interaction' in data:
                if current_time - data['last_interaction'] > timedelta(hours=1):
                    users_to_remove.append(user_id)
        
        for user_id in users_to_remove:
            del user_data[user_id]
            logger.info(f"تم تنظيف بيانات المستخدم {user_id}")
        
        # إرسال تقرير للمدير
        send_admin_report()
        
        logger.info(f"{get_random_emoji()} انتهاء الصيانة الدورية - جلسات نشطة: {bot_stats['active_sessions']}")
        
    except Exception as e:
        logger.error(f"خطأ في الصيانة الدورية: {e}")

def send_admin_report():
    """إرسال تقرير للمدير"""
    try:
        report = f"{get_random_emoji()} **تقرير البوت الدوري**\n\n"
        report += f"📊 **الإحصائيات:**\n"
        report += f"• إجمالي المستخدمين: {bot_stats['total_users']}\n"
        report += f"• إجمالي عمليات البحث: {bot_stats['total_searches']}\n"
        report += f"• الجلسات النشطة: {bot_stats['active_sessions']}\n"
        report += f"• آخر نشاط: {bot_stats['last_activity'].strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        report += f"🔄 **حالة النظام:** ✅ نشط\n"
        report += f"⏰ **الوقت:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        bot.send_message(ADMIN_ID, report, parse_mode='Markdown')
    except Exception as e:
        logger.error(f"خطأ في إرسال التقرير للمدير: {e}")

def start_periodic_tasks():
    """بدء المهام الدورية"""
    def run_scheduler():
        while True:
            schedule.run_pending()
            time.sleep(60)  # التحقق كل دقيقة
    
    # جدولة المهام
    schedule.every(30).minutes.do(periodic_maintenance)
    schedule.every(6).hours.do(send_admin_report)
    
    # تشغيل المجدول في thread منفصل
    scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
    scheduler_thread.start()
    logger.info("تم بدء المهام الدورية للبوت")

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

@app.route('/health', methods=['GET'])
def health_check():
    """فحص صحة البوت"""
    return {
        'status': 'active',
        'timestamp': datetime.now().isoformat(),
        'stats': bot_stats,
        'active_users': len(user_data)
    }

@app.route('/stats', methods=['GET'])
def get_stats():
    """الحصول على إحصائيات البوت"""
    return bot_stats

@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    # تحديث وقت التفاعل الأخير
    if user_id not in user_data:
        user_data[user_id] = {}
    user_data[user_id]['last_interaction'] = datetime.now()
    
    # التحقق من المستخدم الجديد
    if user_id not in new_users:
        new_users.add(user_id)
        update_bot_stats("user")
        notify_admin(user_id, message.from_user.username)
    
    # التحقق من الاشتراك في القنوات
    not_subscribed = check_subscription(user_id)
    
    if not_subscribed:
        markup = InlineKeyboardMarkup()
        # إضافة أزرار للقنوات
        for channel in REQUIRED_CHANNELS:
            markup.add(InlineKeyboardButton(f"{get_random_emoji()} اشترك في {channel}", url=f"https://t.me/{channel[1:]}"))
        markup.add(InlineKeyboardButton("🔍 تحقق من الاشتراك", callback_data="check_subscription"))
        msg = bot.send_message(chat_id, f"{get_random_emoji()} **يجب الاشتراك في القنوات التالية أولاً:**\n" + "\n".join([f"• {channel}" for channel in REQUIRED_CHANNELS]), reply_markup=markup, parse_mode='Markdown')
        # حفظ معرف الرسالة الرئيسية للمستخدم
        user_data[user_id]['main_message_id'] = msg.message_id
    else:
        show_main_menu(chat_id, user_id)

@bot.message_handler(commands=['stats'])
def send_stats(message):
    """إرسال إحصائيات البوت للمدير"""
    user_id = message.from_user.id
    if user_id != ADMIN_ID:
        bot.reply_to(message, "⛔️ هذا الأمر متاح للمدير فقط.")
        return
    
    stats_text = f"{get_random_emoji()} **إحصائيات البوت**\n\n"
    stats_text += f"👥 **المستخدمين:** {bot_stats['total_users']}\n"
    stats_text += f"🔍 **عمليات البحث:** {bot_stats['total_searches']}\n"
    stats_text += f"🔄 **الجلسات النشطة:** {bot_stats['active_sessions']}\n"
    stats_text += f"⏰ **آخر نشاط:** {bot_stats['last_activity'].strftime('%Y-%m-%d %H:%M:%S')}\n"
    stats_text += f"📊 **المستخدمين المخزنين:** {len(user_data)}"
    
    bot.reply_to(message, stats_text, parse_mode='Markdown')

@bot.message_handler(commands=['broadcast'])
def broadcast_message(message):
    """بث رسالة لجميع المستخدمين (للمدير فقط)"""
    user_id = message.from_user.id
    if user_id != ADMIN_ID:
        bot.reply_to(message, "⛔️ هذا الأمر متاح للمدير فقط.")
        return
    
    # استخراج نص الرسالة من الأمر
    broadcast_text = message.text.replace('/broadcast', '').strip()
    if not broadcast_text:
        bot.reply_to(message, "❗️ يرجى إضافة نص الرسالة بعد الأمر /broadcast")
        return
    
    # إضافة ترويسة وتذييلة للرسالة
    formatted_message = f"{get_random_emoji()} **إعلان مهم**\n\n{broadcast_text}\n\n— فريق PEXELBO {get_random_emoji()}"
    
    # إرسال الرسالة لجميع المستخدمين
    sent_count = 0
    failed_count = 0
    
    for user_id in new_users:
        try:
            bot.send_message(user_id, formatted_message, parse_mode='Markdown')
            sent_count += 1
            time.sleep(0.1)  # تجنب حظر التلجرام
        except Exception as e:
            logger.error(f"فشل إرسال الرسالة للمستخدم {user_id}: {e}")
            failed_count += 1
    
    bot.reply_to(message, f"✅ تم إرسال الرسالة لـ {sent_count} مستخدم\n❌ فشل إرسالها لـ {failed_count} مستخدم")

def notify_admin(user_id, username):
    """إرسال إشعار للمدير عند انضمام مستخدم جديد"""
    try:
        username = f"@{username}" if username else "بدون معرف"
        message = f"{get_random_emoji()} مستخدم جديد انضم للبوت:\n\n"
        message += f"🆔 **ID:** {user_id}\n"
        message += f"👤 **Username:** {username}\n"
        message += f"📊 **إجمالي المستخدمين الآن:** {len(new_users)}"
        bot.send_message(ADMIN_ID, message, parse_mode='Markdown')
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
    # تحديث وقت التفاعل الأخير
    user_data[user_id]['last_interaction'] = datetime.now()
    
    # إعادة ضبط بيانات المستخدم
    if user_id not in user_data:
        user_data[user_id] = {}
    
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton(f"{get_random_emoji()} انقر للبحث", callback_data="search"))
    markup.add(InlineKeyboardButton(f"{get_random_emoji()} عن المطور", callback_data="about_dev"))
    markup.add(InlineKeyboardButton(f"📊 إحصائيات البوت", callback_data="bot_stats"))
    
    welcome_msg = f"{get_random_emoji()} **مرحباً بك في PEXELBO**\n\n🔎 ابحث عن الصور والفيديوهات المجانية باللغة الإنجليزية\n\n{get_random_emoji()} **مميزاتنا:**\n• بحث سريع ومجاني\n• صور وفيديوهات عالية الجودة\n• واجهة تفاعلية ممتعة"
    
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
            markup.add(InlineKeyboardButton(f"{get_random_emoji()} اشترك في {channel}", url=f"https://t.me/{channel[1:]}"))
        markup.add(InlineKeyboardButton("✅ تحقق من الاشتراك", callback_data="check_subscription"))
        
        try:
            bot.edit_message_text(
                chat_id=chat_id,
                message_id=call.message.message_id,
                text=f"❌ **لم تشترك بعد في القنوات التالية:**\n" + "\n".join([f"• {channel}" for channel in not_subscribed]),
                reply_markup=markup,
                parse_mode='Markdown'
            )
        except Exception as e:
            logger.error(f"خطأ في تعديل رسالة الاشتراك: {e}")
    else:
        bot.answer_callback_query(call.id, f"{get_random_emoji()} تم الاشتراك بنجاح! يمكنك الآن استخدام البوت.", show_alert=False)
        show_main_menu(chat_id, user_id)

@bot.callback_query_handler(func=lambda call: call.data == "search")
def show_content_types(call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    
    # تحديث وقت التفاعل الأخير
    user_data[user_id]['last_interaction'] = datetime.now()
    
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
    markup.add(InlineKeyboardButton(f"{get_random_emoji()} Photos", callback_data="type_photo"))
    markup.add(InlineKeyboardButton(f"{get_random_emoji()} Vectors", callback_data="type_vector"))
    markup.add(InlineKeyboardButton(f"{get_random_emoji()} Illustrations", callback_data="type_illustration"))
    markup.add(InlineKeyboardButton(f"{get_random_emoji()} Videos", callback_data="type_video"))
    markup.add(InlineKeyboardButton(f"{get_random_emoji()} All", callback_data="type_all"))
    markup.add(InlineKeyboardButton("🔙 رجوع", callback_data="back_to_main"))
    
    try:
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=call.message.message_id,
            text=f"📂 **اختر نوع المحتوى:** {get_random_emoji()}",
            reply_markup=markup,
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"خطأ في عرض انواع المحتوى: {e}")

@bot.callback_query_handler(func=lambda call: call.data.startswith("type_"))
def request_search_term(call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    
    # تحديث وقت التفاعل الأخير
    user_data[user_id]['last_interaction'] = datetime.now()
    
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
            text=f"🔍 **ارسل كلمة البحث باللغة الانجليزية:** {get_random_emoji()}",
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
    
    # تحديث وقت التفاعل الأخير
    user_data[user_id]['last_interaction'] = datetime.now()
    
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
            text=f"⏳ **جاري البحث في قاعدة البيانات...** {get_random_emoji()}",
            reply_markup=None,
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"خطأ في عرض رسالة التحميل: {e}")
    
    # البحث في Pixabay
    results = search_pixabay(search_term, content_type)
    
    # تحديث إحصائيات البحث
    update_bot_stats("search")
    
    if not results or 'hits' not in results or len(results['hits']) == 0:
        # عرض خيارات عند عدم وجود نتائج
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton(f"{get_random_emoji()} بحث جديد", callback_data="search"))
        markup.add(InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="back_to_main"))
        
        try:
            bot.edit_message_text(
                chat_id=chat_id,
                message_id=user_data[user_id]['search_message_id'],
                text=f"❌ **لم يتم العثور على نتائج لكلمة:** `{search_term}`\n\n⚠️ يرجى المحاولة بكلمات أخرى {get_random_emoji()}",
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
        markup.add(InlineKeyboardButton(f"{get_random_emoji()} اشترك في {channel}", url=f"https://t.me/{channel[1:]}"))
    markup.add(InlineKeyboardButton("✅ تحقق من الاشتراك", callback_data="check_subscription"))
    
    bot.send_message(chat_id, f"❗️ **يجب الاشتراك في القنوات أولاً:**\n" + "\n".join([f"• {channel}" for channel in REQUIRED_CHANNELS]), reply_markup=markup, parse_mode='Markdown')

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
                text=f"⏰ **انتهت جلسة البحث، ابدأ بحثاً جديداً** {get_random_emoji()}",
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
                text=f"🏁 **نهاية النتائج** {get_random_emoji()}",
                parse_mode='Markdown'
            )
        except:
            pass
        return
    
    item = results[current_index]
    
    # بناء الرسالة
    caption = f"{get_random_emoji()} **البحث:** {search_term}\n"
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
    
    markup.add(InlineKeyboardButton(f"{get_random_emoji()} تحميل", callback_data="download"))
    markup.add(InlineKeyboardButton(f"{get_random_emoji()} بحث جديد", callback_data="search"))
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
    markup.add(InlineKeyboardButton(f"{get_random_emoji()} بحث جديد", callback_data="search"))
    markup.add(InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="back_to_main"))
    try:
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=user_data[user_id]['search_message_id'],
            text=f"❌ **لم يتم العثور على أي نتائج**\n\n⚠️ يرجى المحاولة بكلمات أخرى {get_random_emoji()}",
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
    
    # تحديث وقت التفاعل الأخير
    user_data[user_id]['last_interaction'] = datetime.now()
    
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
    
    # تحديث وقت التفاعل الأخير
    user_data[user_id]['last_interaction'] = datetime.now()
    
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
    bot.answer_callback_query(call.id, f"{get_random_emoji()} تم التحميل بنجاح!", show_alert=False)
    
    # إظهار خيارات جديدة في رسالة منفصلة
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton(f"{get_random_emoji()} بحث جديد", callback_data="search"))
    markup.add(InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="back_to_main"))
    
    bot.send_message(chat_id, f"✅ **تم تحميل المحتوى بنجاح!** {get_random_emoji()}\n\nماذا تريد أن تفعل الآن؟", reply_markup=markup, parse_mode='Markdown')

@bot.callback_query_handler(func=lambda call: call.data == "bot_stats")
def show_bot_stats(call):
    """عرض إحصائيات البوت للمستخدم"""
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    
    stats_text = f"{get_random_emoji()} **إحصائيات البوت**\n\n"
    stats_text += f"👥 **إجمالي المستخدمين:** {bot_stats['total_users']}\n"
    stats_text += f"🔍 **إجمالي عمليات البحث:** {bot_stats['total_searches']}\n"
    stats_text += f"🔄 **الجلسات النشطة:** {bot_stats['active_sessions']}\n"
    stats_text += f"⏰ **آخر نشاط:** {bot_stats['last_activity'].strftime('%H:%M:%S')}\n\n"
    stats_text += f"🎯 **البوت يعمل بكفاءة!** {get_random_emoji()}"
    
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🔙 رجوع", callback_data="back_to_main"))
    
    try:
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=call.message.message_id,
            text=stats_text,
            reply_markup=markup,
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"خطأ في عرض إحصائيات البوت: {e}")

@bot.callback_query_handler(func=lambda call: call.data == "about_dev")
def show_dev_info(call):
    dev_info = f"""
{get_random_emoji()} **عن المطور** @Ili8_8ill

مطور مبتدئ في عالم بوتات تيليجرام، بدأ رحلته بشغف كبير لتعلم البرمجة وصناعة أدوات ذكية تساعد المستخدمين وتضيف قيمة للمجتمعات الرقمية. يسعى لتطوير مهاراته يومًا بعد يوم من خلال التجربة، التعلم، والمشاركة في مشاريع بسيطة لكنها فعالة.

**ما يميزه في هذه المرحلة:**
• حب الاستكشاف والتعلم الذاتي
• بناء بوتات بسيطة بمهام محددة
• استخدام أدوات مثل BotFather و Python
• الانفتاح على النقد والتطوير المستمر

**القنوات المرتبطة:**
@crazys7 - @AWU87

**رؤية المطور:**
الانطلاق من الأساسيات نحو الاحتراف، خطوة بخطوة، مع طموح لصناعة بوتات تلبي احتياجات حقيقية وتحدث فرقًا.

**للتواصل:**
تابع الحساب @Ili8_8ill

{get_random_emoji()} **شكراً لاستخدامك البوت!**
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
    
    # بدء المهام الدورية
    start_periodic_tasks()
    
    # تعيين ويب هوك
    set_webhook()
    
    # تشغيل التطبيق
    app.run(host='0.0.0.0', port=10000)
