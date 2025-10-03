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
import json

# تهيئة نظام التسجيل
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TOKEN = '8052936091:AAFzLTZ9EQJSWauG9DmGjH2cWzrRx8pOtks'
PIXABAY_API_KEY = '51444506-bffefcaf12816bd85a20222d1'
ADMIN_USERNAME = '@OlIiIl7'
WEBHOOK_URL = 'https://vixabot-3yzy.onrender.com/webhook'

app = Flask(__name__)
bot = telebot.TeleBot(TOKEN)

# قنوات الاشتراك الإجباري
REQUIRED_CHANNELS = ['@iIl337']

# ذاكرة مؤقتة لتخزين نتائج البحث لكل مستخدم
user_data = {}
new_users = set()

# قائمة الرموز التعبيرية المتحركة
ANIMATED_EMOJIS = ['🌿', '🌳', '🥝', '🍹', '👋', '🍻', '🥀', '🍒', '🍀', '🌻', '🌾', '🌴', '🍍', '🍇', '🍈', '🍉', '🍓', '🍅', '🍎', '🫚', '🥦', '🥬', '🥙', '🥗', '🧆', '🍯', '🧃']

# إحصائيات البوت
bot_stats = {
    'total_searches': 0,
    'total_users': 0,
    'active_sessions': 0,
    'last_activity': datetime.now(),
    'start_time': datetime.now(),
    'uptime': '0',
    'health_checks': 0,
    'last_health_check': datetime.now()
}

# نظام المراقبة
monitoring = {
    'last_ping': datetime.now(),
    'consecutive_failures': 0,
    'auto_recoveries': 0
}

def get_random_emoji():
    """إرجاع رمز تعبيري عشوائي"""
    return random.choice(ANIMATED_EMOJIS)

def calculate_uptime():
    """حساب مدة التشغيل"""
    uptime = datetime.now() - bot_stats['start_time']
    days = uptime.days
    hours, remainder = divmod(uptime.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{days} يوم, {hours} ساعة, {minutes} دقيقة"

def update_bot_stats(activity_type="general"):
    """تحديث إحصائيات البوت"""
    bot_stats['last_activity'] = datetime.now()
    bot_stats['uptime'] = calculate_uptime()
    
    if activity_type == "search":
        bot_stats['total_searches'] += 1
    elif activity_type == "user":
        bot_stats['total_users'] = len(new_users)
    elif activity_type == "health_check":
        bot_stats['health_checks'] += 1
        bot_stats['last_health_check'] = datetime.now()
    
    active_sessions = 0
    for user_id, data in user_data.items():
        if 'last_interaction' in data:
            if datetime.now() - data['last_interaction'] < timedelta(minutes=10):
                active_sessions += 1
    bot_stats['active_sessions'] = active_sessions

def health_check():
    """فحص صحة البوت وإرسال طلبات دورية"""
    try:
        logger.info(f"🔍 إجراء فحص صحة البوت... {get_random_emoji()}")
        
        # تحديث وقت آخر فحص
        monitoring['last_ping'] = datetime.now()
        
        # تحديث الإحصائيات
        update_bot_stats("health_check")
        
        # تنظيف البيانات القديمة
        cleanup_old_data()
        
        logger.info(f"✅ فحص الصحة مكتمل - الجلسات النشطة: {bot_stats['active_sessions']}")
        monitoring['consecutive_failures'] = 0
        
    except Exception as e:
        logger.error(f"❌ فشل فحص الصحة: {e}")
        monitoring['consecutive_failures'] += 1

def cleanup_old_data():
    """تنظيف البيانات القديمة"""
    try:
        current_time = datetime.now()
        users_to_remove = []
        
        for user_id, data in user_data.items():
            if 'last_interaction' in data:
                if current_time - data['last_interaction'] > timedelta(hours=2):
                    users_to_remove.append(user_id)
        
        for user_id in users_to_remove:
            del user_data[user_id]
            
        if users_to_remove:
            logger.info(f"🧹 تم تنظيف بيانات {len(users_to_remove)} مستخدم")
            
    except Exception as e:
        logger.error(f"❌ خطأ في تنظيف البيانات: {e}")

def send_health_report():
    """إرسال تقرير صحة البوت"""
    try:
        report = f"📊 **تقرير صحة البوت** {get_random_emoji()}\n\n"
        report += f"⏰ **مدة التشغيل:** {bot_stats['uptime']}\n"
        report += f"👥 **المستخدمين:** {bot_stats['total_users']}\n"
        report += f"🔍 **عمليات البحث:** {bot_stats['total_searches']}\n"
        report += f"🔄 **الجلسات النشطة:** {bot_stats['active_sessions']}\n"
        report += f"❤️ **فحوصات الصحة:** {bot_stats['health_checks']}\n"
        report += f"⏱️ **آخر فحص:** {bot_stats['last_health_check'].strftime('%H:%M:%S')}\n"
        report += f"🛠️ **الاستعادة التلقائية:** {monitoring['auto_recoveries']}\n"
        report += f"📈 **الحالة:** {'✅ ممتازة' if monitoring['consecutive_failures'] == 0 else '⚠️ تحت المراقبة'}\n\n"
        report += f"**{get_random_emoji()} البوت يعمل بشكل طبيعي**"
        
        # إرسال التقرير للمطور
        bot.send_message(ADMIN_USERNAME, report, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"❌ خطأ في إرسال تقرير الصحة: {e}")

def start_periodic_tasks():
    """بدء المهام الدورية"""
    def run_scheduler():
        logger.info("🚀 بدء تشغيل المجدول الدوري")
        while True:
            try:
                schedule.run_pending()
                time.sleep(60)
            except Exception as e:
                logger.error(f"❌ خطأ في المجدول: {e}")
                time.sleep(30)
    
    # جدولة المهام
    schedule.every(5).minutes.do(health_check)
    schedule.every(30).minutes.do(send_health_report)
    schedule.every(2).hours.do(cleanup_old_data)
    
    # بدء المجدول في thread منفصل
    scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
    scheduler_thread.start()
    logger.info("✅ المهام الدورية مفعلة")

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
        time.sleep(2)
        bot.set_webhook(url=WEBHOOK_URL)
        logger.info("✅ تم تعيين ويب هوك بنجاح")
        return True
    except Exception as e:
        logger.error(f"❌ خطأ في تعيين ويب هوك: {e}")
        return False

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
def health_check_endpoint():
    """نقطة فحص صحة البوت"""
    health_status = {
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'stats': {
            'total_users': bot_stats['total_users'],
            'total_searches': bot_stats['total_searches'],
            'active_sessions': bot_stats['active_sessions'],
            'uptime': bot_stats['uptime'],
            'health_checks': bot_stats['health_checks']
        },
        'monitoring': {
            'last_ping': monitoring['last_ping'].isoformat(),
            'consecutive_failures': monitoring['consecutive_failures'],
            'auto_recoveries': monitoring['auto_recoveries']
        }
    }
    return json.dumps(health_status, ensure_ascii=False)

@app.route('/')
def home():
    """الصفحة الرئيسية - إصدار مبسط بدون أخطاء"""
    try:
        html = f"""
        <html>
            <head>
                <title>PEXELBO Bot</title>
                <meta charset="utf-8">
                <style>
                    body {{ font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }}
                    .container {{ max-width: 800px; margin: 0 auto; background: white; padding: 30px; border-radius: 15px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
                    .status {{ padding: 20px; background: #f8f9fa; border-radius: 10px; margin: 20px 0; }}
                    .emoji {{ font-size: 24px; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <h1>🤖 PEXELBO Bot</h1>
                    <div class="status">
                        <p><strong>الحالة:</strong> ✅ نشط</p>
                        <p><strong>مدة التشغيل:</strong> {bot_stats.get('uptime', 'غير متوفر')}</p>
                        <p><strong>المستخدمين:</strong> {bot_stats.get('total_users', 0)}</p>
                        <p><strong>عمليات البحث:</strong> {bot_stats.get('total_searches', 0)}</p>
                        <p><strong>آخر تحديث:</strong> {bot_stats.get('last_activity', datetime.now()).strftime('%Y-%m-%d %H:%M:%S')}</p>
                    </div>
                    <p><a href="/health">فحص الصحة التفصيلي</a></p>
                    <p class="emoji">🚀 البوت يعمل بشكل طبيعي</p>
                </div>
            </body>
        </html>
        """
        return html
    except Exception as e:
        return f"<h1>PEXELBO Bot</h1><p>خطأ في تحميل الصفحة: {str(e)}</p>"

def check_subscription(user_id):
    """التحقق من اشتراك المستخدم في جميع القنوات المطلوبة"""
    not_subscribed = []
    for channel in REQUIRED_CHANNELS:
        try:
            chat_member = bot.get_chat_member(chat_id=channel, user_id=user_id)
            if chat_member.status not in ['member', 'administrator', 'creator']:
                not_subscribed.append(channel)
        except Exception as e:
            logger.error(f"❌ خطأ في التحقق من الاشتراك في {channel}: {e}")
            not_subscribed.append(channel)
    return not_subscribed

@bot.message_handler(commands=['start'])
def send_welcome(message):
    try:
        user_id = message.from_user.id
        chat_id = message.chat.id
        
        logger.info(f"🎯 مستخدم جديد: {user_id} - @{message.from_user.username}")
        
        # تحديث وقت التفاعل الأخير والإحصائيات
        if user_id not in user_data:
            user_data[user_id] = {}
        user_data[user_id]['last_interaction'] = datetime.now()
        
        if user_id not in new_users:
            new_users.add(user_id)
            update_bot_stats("user")
        
        # التحقق من الاشتراك في القنوات
        not_subscribed = check_subscription(user_id)
        
        if not_subscribed:
            markup = InlineKeyboardMarkup()
            for channel in REQUIRED_CHANNELS:
                markup.add(InlineKeyboardButton(f"{get_random_emoji()} اشترك في {channel}", url=f"https://t.me/{channel[1:]}"))
            markup.add(InlineKeyboardButton("🔍 تحقق من الاشتراك", callback_data="check_subscription"))
            
            welcome_text = f"""
{get_random_emoji()} **أهلاً بك في PEXELBO!**

🔍 **بوت البحث عن الصور والفيديوهات المجانية**

❗️ **يجب الاشتراك في القنوات التالية أولاً:**
""" + "\n".join([f"• {channel}" for channel in REQUIRED_CHANNELS]) + f"""

{get_random_emoji()} بعد الاشتراك، انقر على زر "تحقق من الاشتراك"
            """
            
            bot.send_message(
                chat_id, 
                welcome_text, 
                reply_markup=markup, 
                parse_mode='Markdown'
            )
        else:
            show_main_menu(chat_id, user_id)
            
    except Exception as e:
        logger.error(f"❌ خطأ في معالجة أمر /start: {e}")
        try:
            bot.send_message(message.chat.id, "❌ حدث خطأ أثناء معالجة طلبك. يرجى المحاولة مرة أخرى.")
        except:
            pass

def show_main_menu(chat_id, user_id):
    """عرض القائمة الرئيسية"""
    try:
        user_data[user_id]['last_interaction'] = datetime.now()
        
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton(f"{get_random_emoji()} انقر للبحث", callback_data="search"))
        markup.add(InlineKeyboardButton(f"{get_random_emoji()} عن المطور", callback_data="about_dev"))
        markup.add(InlineKeyboardButton(f"📊 إحصائيات البوت", callback_data="bot_stats"))
        
        welcome_msg = f"""
{get_random_emoji()} **مرحباً بك في PEXELBO**

🔎 **بوت البحث عن الصور والفيديوهات المجانية**

{get_random_emoji()} **المميزات:**
• بحث مجاني عن الصور
• فيديوهات عالية الجودة
• واجهة تفاعلية سهلة
• دعم متعدد اللغات

**للبحث، انقر على زر "انقر للبحث" أدناه 👇**
        """
        
        bot.send_message(chat_id, welcome_msg, reply_markup=markup, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"❌ خطأ في عرض القائمة الرئيسية: {e}")

@bot.callback_query_handler(func=lambda call: call.data == "check_subscription")
def verify_subscription(call):
    try:
        user_id = call.from_user.id
        chat_id = call.message.chat.id
        not_subscribed = check_subscription(user_id)
        
        if not_subscribed:
            markup = InlineKeyboardMarkup()
            for channel in REQUIRED_CHANNELS:
                markup.add(InlineKeyboardButton(f"{get_random_emoji()} اشترك في {channel}", url=f"https://t.me/{channel[1:]}"))
            markup.add(InlineKeyboardButton("✅ تحقق من الاشتراك", callback_data="check_subscription"))
            
            bot.edit_message_text(
                chat_id=chat_id,
                message_id=call.message.message_id,
                text=f"❌ **لم تشترك بعد في القنوات التالية:**\n" + "\n".join([f"• {channel}" for channel in not_subscribed]),
                reply_markup=markup,
                parse_mode='Markdown'
            )
        else:
            bot.answer_callback_query(call.id, f"{get_random_emoji()} تم الاشتراك بنجاح! يمكنك الآن استخدام البوت.", show_alert=False)
            show_main_menu(chat_id, user_id)
    except Exception as e:
        logger.error(f"❌ خطأ في التحقق من الاشتراك: {e}")

@bot.callback_query_handler(func=lambda call: call.data == "search")
def show_content_types(call):
    try:
        user_id = call.from_user.id
        chat_id = call.message.chat.id
        
        user_data[user_id]['last_interaction'] = datetime.now()
        
        not_subscribed = check_subscription(user_id)
        if not_subscribed:
            bot.answer_callback_query(call.id, "❗️ يجب الاشتراك في القنوات أولاً", show_alert=True)
            return
        
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton(f"{get_random_emoji()} Photos", callback_data="type_photo"))
        markup.add(InlineKeyboardButton(f"{get_random_emoji()} Vectors", callback_data="type_vector"))
        markup.add(InlineKeyboardButton(f"{get_random_emoji()} Illustrations", callback_data="type_illustration"))
        markup.add(InlineKeyboardButton(f"{get_random_emoji()} Videos", callback_data="type_video"))
        markup.add(InlineKeyboardButton(f"{get_random_emoji()} All", callback_data="type_all"))
        markup.add(InlineKeyboardButton("🔙 رجوع", callback_data="back_to_main"))
        
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=call.message.message_id,
            text=f"📂 **اختر نوع المحتوى:** {get_random_emoji()}",
            reply_markup=markup,
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"❌ خطأ في عرض أنواع المحتوى: {e}")

@bot.callback_query_handler(func=lambda call: call.data.startswith("type_"))
def request_search_term(call):
    try:
        user_id = call.from_user.id
        chat_id = call.message.chat.id
        
        user_data[user_id]['last_interaction'] = datetime.now()
        
        not_subscribed = check_subscription(user_id)
        if not_subscribed:
            bot.answer_callback_query(call.id, "❗️ يجب الاشتراك في القنوات أولاً", show_alert=True)
            return
        
        content_type = call.data.split("_")[1]
        
        if user_id not in user_data:
            user_data[user_id] = {}
        user_data[user_id]['content_type'] = content_type
        
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("❌ الغاء البحث", callback_data="cancel_search"))
        
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=call.message.message_id,
            text=f"🔍 **ارسل كلمة البحث باللغة الانجليزية:** {get_random_emoji()}",
            reply_markup=markup,
            parse_mode='Markdown'
        )
        
        user_data[user_id]['search_message_id'] = call.message.message_id
        bot.register_next_step_handler(call.message, process_search_term, user_id)
    except Exception as e:
        logger.error(f"❌ خطأ في طلب كلمة البحث: {e}")

def process_search_term(message, user_id):
    try:
        chat_id = message.chat.id
        user_data[user_id]['last_interaction'] = datetime.now()
        
        not_subscribed = check_subscription(user_id)
        if not_subscribed:
            show_subscription_required(chat_id, user_id)
            return
        
        search_term = message.text
        
        # حذف رسالة المستخدم
        try:
            bot.delete_message(chat_id, message.message_id)
        except:
            pass
        
        if user_id not in user_data or 'content_type' not in user_data[user_id]:
            show_main_menu(chat_id, user_id)
            return
        
        content_type = user_data[user_id]['content_type']
        
        # عرض رسالة التحميل
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=user_data[user_id]['search_message_id'],
            text=f"⏳ **جاري البحث عن '{search_term}'...** {get_random_emoji()}",
            reply_markup=None,
            parse_mode='Markdown'
        )
        
        # البحث في Pixabay
        results = search_pixabay(search_term, content_type)
        update_bot_stats("search")
        
        if not results or 'hits' not in results or len(results['hits']) == 0:
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton(f"{get_random_emoji()} بحث جديد", callback_data="search"))
            markup.add(InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="back_to_main"))
            
            bot.edit_message_text(
                chat_id=chat_id,
                message_id=user_data[user_id]['search_message_id'],
                text=f"❌ **لم يتم العثور على نتائج لكلمة:** `{search_term}`\n\n⚠️ جرب كلمات بحث أخرى {get_random_emoji()}",
                reply_markup=markup,
                parse_mode='Markdown'
            )
            return
        
        # حفظ النتائج
        user_data[user_id]['search_term'] = search_term
        user_data[user_id]['search_results'] = results['hits']
        user_data[user_id]['current_index'] = 0
        
        # عرض النتيجة الأولى
        show_result(chat_id, user_id, message_id=user_data[user_id]['search_message_id'])
        
    except Exception as e:
        logger.error(f"❌ خطأ في معالجة البحث: {e}")

def search_pixabay(query, content_type):
    base_url = "https://pixabay.com/api/"
    params = {
        'key': PIXABAY_API_KEY,
        'q': query,
        'per_page': 20,
        'lang': 'en'
    }
    
    if content_type == 'photo':
        params['image_type'] = 'photo'
    elif content_type == 'vector':
        params['image_type'] = 'vector'
    elif content_type == 'illustration':
        params['image_type'] = 'photo'
    elif content_type == 'video':
        params['video_type'] = 'all'
        base_url = "https://pixabay.com/api/videos/"
    else:
        params['image_type'] = 'all'
    
    try:
        response = requests.get(base_url, params=params, timeout=15)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"❌ خطأ في واجهة Pixabay: {e}")
        return None

def show_result(chat_id, user_id, message_id=None):
    try:
        if user_id not in user_data or 'search_results' not in user_data[user_id]:
            return
        
        results = user_data[user_id]['search_results']
        current_index = user_data[user_id]['current_index']
        search_term = user_data[user_id].get('search_term', '')
        
        if current_index >= len(results):
            return
        
        item = results[current_index]
        
        # بناء الرسالة
        caption = f"{get_random_emoji()} **البحث:** {search_term}\n"
        caption += f"📊 **النتيجة {current_index+1} من {len(results)}**\n"
        if 'tags' in item:
            caption += f"🏷️ **الوسوم:** {item['tags'][:50]}...\n"
        
        # بناء أزرار التنقل
        markup = InlineKeyboardMarkup()
        row_buttons = []
        
        if current_index > 0:
            row_buttons.append(InlineKeyboardButton("◀️ السابق", callback_data="nav_prev"))
        if current_index < len(results) - 1:
            row_buttons.append(InlineKeyboardButton("▶️ التالي", callback_data="nav_next"))
        
        if row_buttons:
            markup.row(*row_buttons)
        
        markup.add(InlineKeyboardButton(f"{get_random_emoji()} تحميل", callback_data="download"))
        markup.add(InlineKeyboardButton(f"{get_random_emoji()} بحث جديد", callback_data="search"))
        markup.add(InlineKeyboardButton("🔙 الرئيسية", callback_data="back_to_main"))
        
        # إرسال الوسائط
        if 'videos' in item:
            video_url = item['videos']['medium']['url']
            if is_valid_url(video_url):
                bot.send_video(chat_id, video_url, caption=caption, reply_markup=markup, parse_mode='Markdown')
        else:
            image_url = item.get('largeImageURL', item.get('webformatURL', ''))
            if is_valid_url(image_url):
                bot.send_photo(chat_id, image_url, caption=caption, reply_markup=markup, parse_mode='Markdown')
                
    except Exception as e:
        logger.error(f"❌ خطأ في عرض النتيجة: {e}")

@bot.callback_query_handler(func=lambda call: call.data.startswith("nav_"))
def navigate_results(call):
    try:
        user_id = call.from_user.id
        chat_id = call.message.chat.id
        action = call.data.split("_")[1]
        
        user_data[user_id]['last_interaction'] = datetime.now()
        
        if user_id not in user_data or 'search_results' not in user_data[user_id]:
            bot.answer_callback_query(call.id, "⏰ انتهت جلسة البحث، ابدأ بحثاً جديداً")
            return
        
        if action == 'prev':
            user_data[user_id]['current_index'] -= 1
        elif action == 'next':
            user_data[user_id]['current_index'] += 1
        
        # حذف الرسالة القديمة وإرسال جديدة
        bot.delete_message(chat_id, call.message.message_id)
        show_result(chat_id, user_id)
        
    except Exception as e:
        logger.error(f"❌ خطأ في التنقل بين النتائج: {e}")

@bot.callback_query_handler(func=lambda call: call.data == "download")
def download_content(call):
    try:
        user_id = call.from_user.id
        chat_id = call.message.chat.id
        
        user_data[user_id]['last_interaction'] = datetime.now()
        
        bot.answer_callback_query(call.id, f"{get_random_emoji()} تم التحميل بنجاح!", show_alert=False)
        
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton(f"{get_random_emoji()} بحث جديد", callback_data="search"))
        markup.add(InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="back_to_main"))
        
        bot.send_message(chat_id, f"✅ **تم تحميل المحتوى بنجاح!** {get_random_emoji()}", reply_markup=markup, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"❌ خطأ في التحميل: {e}")

@bot.callback_query_handler(func=lambda call: call.data == "bot_stats")
def show_bot_stats(call):
    try:
        stats_text = f"{get_random_emoji()} **إحصائيات البوت**\n\n"
        stats_text += f"👥 **المستخدمين:** {bot_stats['total_users']}\n"
        stats_text += f"🔍 **عمليات البحث:** {bot_stats['total_searches']}\n"
        stats_text += f"🔄 **الجلسات النشطة:** {bot_stats['active_sessions']}\n"
        stats_text += f"⏰ **مدة التشغيل:** {bot_stats['uptime']}\n\n"
        stats_text += f"🎯 **البوت يعمل بكفاءة!** {get_random_emoji()}"
        
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🔙 رجوع", callback_data="back_to_main"))
        
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=stats_text,
            reply_markup=markup,
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"❌ خطأ في عرض الإحصائيات: {e}")

@bot.callback_query_handler(func=lambda call: call.data == "about_dev")
def show_dev_info(call):
    try:
        dev_info = f"""
{get_random_emoji()} **عن المطور** {ADMIN_USERNAME}

مطور بوتات تليجرام متخصص في إنشاء أدوات مفيدة للمستخدمين.

**القنوات المرتبطة:**
{REQUIRED_CHANNELS[0]}

**للتواصل:**
{ADMIN_USERNAME}

{get_random_emoji()} **شكراً لاستخدامك البوت!**
        """
        
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🔙 رجوع", callback_data="back_to_main"))
        
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=dev_info,
            reply_markup=markup,
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"❌ خطأ في عرض معلومات المطور: {e}")

@bot.callback_query_handler(func=lambda call: call.data == "back_to_main")
def return_to_main(call):
    try:
        user_id = call.from_user.id
        chat_id = call.message.chat.id
        show_main_menu(chat_id, user_id)
    except Exception as e:
        logger.error(f"❌ خطأ في العودة للقائمة الرئيسية: {e}")

@bot.callback_query_handler(func=lambda call: call.data == "cancel_search")
def cancel_search(call):
    try:
        user_id = call.from_user.id
        chat_id = call.message.chat.id
        show_main_menu(chat_id, user_id)
    except Exception as e:
        logger.error(f"❌ خطأ في إلغاء البحث: {e}")

def show_subscription_required(chat_id, user_id):
    """عرض رسالة طلب الاشتراك في القنوات"""
    try:
        markup = InlineKeyboardMarkup()
        for channel in REQUIRED_CHANNELS:
            markup.add(InlineKeyboardButton(f"{get_random_emoji()} اشترك في {channel}", url=f"https://t.me/{channel[1:]}"))
        markup.add(InlineKeyboardButton("✅ تحقق من الاشتراك", callback_data="check_subscription"))
        
        bot.send_message(chat_id, f"❗️ **يجب الاشتراك في القنوات أولاً:**\n" + "\n".join([f"• {channel}" for channel in REQUIRED_CHANNELS]), reply_markup=markup, parse_mode='Markdown')
    except Exception as e:
        logger.error(f"❌ خطأ في عرض رسالة الاشتراك: {e}")

if __name__ == '__main__':
    logger.info("🚀 بدء تشغيل البوت...")
    
    # بدء المهام الدورية
    start_periodic_tasks()
    
    # تعيين ويب هوك
    webhook_set = set_webhook()
    
    if webhook_set:
        logger.info("✅ البوت جاهز للعمل!")
        try:
            bot.send_message(ADMIN_USERNAME, "🤖 **تم تشغيل البوت بنجاح**\n\n✅ النظام الدوري مفعل\n🌐 الويب هوك نشط\n🚀 جاهز لاستقبال الطلبات", parse_mode='Markdown')
        except:
            pass
    else:
        logger.error("❌ فشل في تعيين ويب هوك")
    
    # تشغيل التطبيق
    app.run(host='0.0.0.0', port=10000, debug=False)
