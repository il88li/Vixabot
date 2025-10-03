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
        
        # إجراء طلبات اختبارية للحفاظ على النشاط
        test_requests()
        
        # تحديث الإحصائيات
        update_bot_stats("health_check")
        
        # تنظيف البيانات القديمة
        cleanup_old_data()
        
        # التحقق من حالة الويب هوك
        check_webhook_status()
        
        logger.info(f"✅ فحص الصحة مكتمل - الجلسات النشطة: {bot_stats['active_sessions']}")
        monitoring['consecutive_failures'] = 0
        
    except Exception as e:
        logger.error(f"❌ فشل فحص الصحة: {e}")
        monitoring['consecutive_failures'] += 1
        attempt_auto_recovery()

def test_requests():
    """إرسال طلبات اختبارية للحفاظ على نشاط البوت"""
    try:
        # طلب اختباري إلى Pixabay للحفاظ على اتصال API
        test_url = "https://pixabay.com/api/"
        params = {
            'key': PIXABAY_API_KEY,
            'q': 'test',
            'per_page': 1
        }
        response = requests.get(test_url, params=params, timeout=10)
        if response.status_code == 200:
            logger.debug("✅ طلب اختبار Pixabay ناجح")
        
        # طلب اختباري داخلي
        with app.test_client() as client:
            client.get('/health')
            
    except Exception as e:
        logger.warning(f"⚠️ طلب اختباري فاشل: {e}")

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
            logger.info(f"🧹 تم تنظيف بيانات المستخدم {user_id}")
            
        logger.info(f"✅ تنظيف البيانات مكتمل - تمت إزالة {len(users_to_remove)} مستخدم")
        
    except Exception as e:
        logger.error(f"❌ خطأ في تنظيف البيانات: {e}")

def check_webhook_status():
    """التحقق من حالة الويب هوك"""
    try:
        # الحصول على معلومات الويب هوك
        webhook_info = bot.get_webhook_info()
        if webhook_info.url:
            logger.info(f"🌐 الويب هوك نشط: {webhook_info.url}")
            if webhook_info.pending_update_count > 10:
                logger.warning(f"⚠️ هناك {webhook_info.pending_update_count} تحديث معلق")
        else:
            logger.warning("⚠️ الويب هوك غير نشط، إعادة التعيين...")
            set_webhook()
            
    except Exception as e:
        logger.error(f"❌ خطأ في التحقق من حالة الويب هوك: {e}")

def attempt_auto_recovery():
    """محاولة الاستعادة التلقائية في حالة الفشل المتكرر"""
    if monitoring['consecutive_failures'] >= 3:
        try:
            logger.warning("🔄 محاولة استعادة تلقائية...")
            
            # إعادة تعيين الويب هوك
            set_webhook()
            
            # إعادة تعيين بعض المتغيرات
            monitoring['consecutive_failures'] = 0
            monitoring['auto_recoveries'] += 1
            
            logger.info("✅ الاستعادة التلقائية مكتملة")
            
        except Exception as e:
            logger.error(f"❌ فشل الاستعادة التلقائية: {e}")

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
                time.sleep(60)  # التحقق كل دقيقة
            except Exception as e:
                logger.error(f"❌ خطأ في المجدول: {e}")
                time.sleep(30)
    
    # جدولة المهام
    schedule.every(5).minutes.do(health_check)  # فحص صحة كل 5 دقائق
    schedule.every(30).minutes.do(send_health_report)  # تقرير كل 30 دقيقة
    schedule.every(2).hours.do(cleanup_old_data)  # تنظيف كل ساعتين
    schedule.every(6).hours.do(check_webhook_status)  # فحص ويب هوك كل 6 ساعات
    
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
    except Exception as e:
        logger.error(f"❌ خطأ في تعيين ويب هوك: {e}")

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
    """الصفحة الرئيسية"""
    return """
    <html>
        <head>
            <title>PEXELBO Bot</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 40px; }
                .status { padding: 20px; background: #f0f0f0; border-radius: 10px; }
            </style>
        </head>
        <body>
            <h1>🤖 PEXELBO Bot</h1>
            <div class="status">
                <p><strong>الحالة:</strong> ✅ نشط</p>
                <p><strong>مدة التشغيل:</strong> {}</p>
                <p><strong>المستخدمين:</strong> {}</p>
                <p><strong>آخر تحديث:</strong> {}</p>
            </div>
            <p><a href="/health">فحص الصحة التفصيلي</a></p>
        </body>
    </html>
    """.format(
        bot_stats['uptime'],
        bot_stats['total_users'],
        bot_stats['last_activity'].strftime('%Y-%m-%d %H:%M:%S')
    )

# باقي دوال البوت (send_welcome, show_main_menu, etc.) تبقى كما هي بدون تغيير
# [يتبع نفس الدوال السابقة مع تحسينات بسيطة]

@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    
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
        
        bot.send_message(
            chat_id, 
            f"{get_random_emoji()} **يجب الاشتراك في القنوات التالية أولاً:**\n" + "\n".join([f"• {channel}" for channel in REQUIRED_CHANNELS]), 
            reply_markup=markup, 
            parse_mode='Markdown'
        )
    else:
        show_main_menu(chat_id, user_id)

def show_main_menu(chat_id, user_id):
    """عرض القائمة الرئيسية - دائماً نرسل رسالة جديدة"""
    user_data[user_id]['last_interaction'] = datetime.now()
    
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton(f"{get_random_emoji()} انقر للبحث", callback_data="search"))
    markup.add(InlineKeyboardButton(f"{get_random_emoji()} عن المطور", callback_data="about_dev"))
    markup.add(InlineKeyboardButton(f"📊 إحصائيات البوت", callback_data="bot_stats"))
    
    welcome_msg = f"""
{get_random_emoji()} **مرحباً بك في PEXELBO**

🔎 ابحث عن الصور والفيديوهات المجانية باللغة الإنجليزية

{get_random_emoji()} **مميزاتنا:**
• بحث سريع ومجاني
• صور وفيديوهات عالية الجودة  
• واجهة تفاعلية ممتعة
• نظام مراقبة مستمر {get_random_emoji()}

**للبحث، انقر على زر "انقر للبحث" أدناه 👇**
    """
    
    bot.send_message(chat_id, welcome_msg, reply_markup=markup, parse_mode='Markdown')

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

# [يتبع باقي الدوال بدون تغييرات جذرية]

@bot.callback_query_handler(func=lambda call: call.data == "bot_stats")
def show_bot_stats(call):
    """عرض إحصائيات البوت للمستخدم"""
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    
    stats_text = f"{get_random_emoji()} **إحصائيات البوت**\n\n"
    stats_text += f"👥 **إجمالي المستخدمين:** {bot_stats['total_users']}\n"
    stats_text += f"🔍 **إجمالي عمليات البحث:** {bot_stats['total_searches']}\n"
    stats_text += f"🔄 **الجلسات النشطة:** {bot_stats['active_sessions']}\n"
    stats_text += f"⏰ **مدة التشغيل:** {bot_stats['uptime']}\n"
    stats_text += f"❤️ **فحوصات الصحة:** {bot_stats['health_checks']}\n\n"
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
        logger.error(f"❌ خطأ في عرض إحصائيات البوت: {e}")

@bot.callback_query_handler(func=lambda call: call.data == "about_dev")
def show_dev_info(call):
    dev_info = f"""
{get_random_emoji()} **عن المطور** {ADMIN_USERNAME}

مطور مبتدئ في عالم بوتات تيليجرام، بدأ رحلته بشغف كبير لتعلم البرمجة وصناعة أدوات ذكية تساعد المستخدمين وتضيف قيمة للمجتمعات الرقمية.

**نظام المراقبة:**
• فحوصات صحة دورية {get_random_emoji()}
• استعادة تلقائية في حالة الأخطاء
• إحصائيات حية ومحدثة
• تنظيف تلقائي للبيانات

**القنوات المرتبطة:**
{REQUIRED_CHANNELS[0]}

**رؤية المطور:**
الانطلاق من الأساسيات نحو الاحتراف، خطوة بخطوة، مع طموح لصناعة بوتات تلبي احتياجات حقيقية وتحدث فرقًا.

**للتواصل:**
تابع الحساب {ADMIN_USERNAME}

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
        logger.error(f"❌ خطأ في عرض معلومات المطور: {e}")

# [باقي الدوال تبقى كما هي]

if __name__ == '__main__':
    logger.info("🚀 بدء تشغيل البوت مع نظام المراقبة المحسن...")
    
    # بدء المهام الدورية
    start_periodic_tasks()
    
    # تعيين ويب هوك
    set_webhook()
    
    # إرسال رسالة بدء التشغيل
    try:
        startup_msg = f"🤖 **تم تشغيل البوت بنجاح**\n\n⏰ **الوقت:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n🔧 **الإصدار:** نظام مراقبة محسن\n✅ **الحالة:** جاهز للعمل\n\n{get_random_emoji()} **تم تفعيل النظام الدوري**"
        bot.send_message(ADMIN_USERNAME, startup_msg, parse_mode='Markdown')
    except Exception as e:
        logger.error(f"❌ لا يمكن إرسال رسالة البدء: {e}")
    
    # تشغيل التطبيق
    app.run(host='0.0.0.0', port=10000, debug=False)
