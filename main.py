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
ADMIN_USERNAME = '@OlIiIl7'  # معرف المدير الجديد
WEBHOOK_URL = 'https://vixabot-3yzy.onrender.com/webhook'

app = Flask(__name__)
bot = telebot.TeleBot(TOKEN)

# قنوات الاشتراك الإجباري
REQUIRED_CHANNELS = ['@iIl337']  # القناة المحدثة

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
    
    active_sessions = 0
    for user_id, data in user_data.items():
        if 'last_interaction' in data:
            if datetime.now() - data['last_interaction'] < timedelta(minutes=10):
                active_sessions += 1
    bot_stats['active_sessions'] = active_sessions

def periodic_maintenance():
    """وظيفة الصيانة الدورية للبوت"""
    try:
        logger.info(f"{get_random_emoji()} بدء الصيانة الدورية للبوت")
        update_bot_stats()
        
        current_time = datetime.now()
        users_to_remove = []
        for user_id, data in user_data.items():
            if 'last_interaction' in data:
                if current_time - data['last_interaction'] > timedelta(hours=1):
                    users_to_remove.append(user_id)
        
        for user_id in users_to_remove:
            del user_data[user_id]
            logger.info(f"تم تنظيف بيانات المستخدم {user_id}")
        
        logger.info(f"{get_random_emoji()} انتهاء الصيانة الدورية - جلسات نشطة: {bot_stats['active_sessions']}")
        
    except Exception as e:
        logger.error(f"خطأ في الصيانة الدورية: {e}")

def start_periodic_tasks():
    """بدء المهام الدورية"""
    def run_scheduler():
        while True:
            schedule.run_pending()
            time.sleep(60)
    
    schedule.every(30).minutes.do(periodic_maintenance)
    
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
    
    # التحقق من الاشتراك في القنوات
    not_subscribed = check_subscription(user_id)
    
    if not_subscribed:
        markup = InlineKeyboardMarkup()
        for channel in REQUIRED_CHANNELS:
            markup.add(InlineKeyboardButton(f"{get_random_emoji()} اشترك في {channel}", url=f"https://t.me/{channel[1:]}"))
        markup.add(InlineKeyboardButton("🔍 تحقق من الاشتراك", callback_data="check_subscription"))
        
        # دائماً نرسل رسالة جديدة
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

**للبحث، انقر على زر "انقر للبحث" أدناه 👇**
    """
    
    # دائماً نرسل رسالة جديدة بدلاً من تعديل القديمة
    bot.send_message(chat_id, welcome_msg, reply_markup=markup, parse_mode='Markdown')

@bot.callback_query_handler(func=lambda call: call.data == "check_subscription")
def verify_subscription(call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    not_subscribed = check_subscription(user_id)
    
    if not_subscribed:
        markup = InlineKeyboardMarkup()
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
    
    user_data[user_id]['last_interaction'] = datetime.now()
    
    not_subscribed = check_subscription(user_id)
    if not_subscribed:
        bot.answer_callback_query(call.id, "❗️ يجب الاشتراك في القنوات أولاً", show_alert=True)
        return
    
    if user_id not in user_data:
        user_data[user_id] = {}
    
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
    
    user_data[user_id]['search_message_id'] = call.message.message_id
    bot.register_next_step_handler(call.message, process_search_term, user_id)

@bot.callback_query_handler(func=lambda call: call.data == "cancel_search")
def cancel_search(call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    show_main_menu(chat_id, user_id)

def process_search_term(message, user_id):
    chat_id = message.chat.id
    
    user_data[user_id]['last_interaction'] = datetime.now()
    
    not_subscribed = check_subscription(user_id)
    if not_subscribed:
        show_subscription_required(chat_id, user_id)
        return
    
    search_term = message.text
    
    try:
        bot.delete_message(chat_id, message.message_id)
    except Exception as e:
        logger.error(f"خطأ في حذف رسالة المستخدم: {e}")
    
    if user_id not in user_data or 'content_type' not in user_data[user_id]:
        show_main_menu(chat_id, user_id)
        return
    
    content_type = user_data[user_id]['content_type']
    
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
    
    results = search_pixabay(search_term, content_type)
    update_bot_stats("search")
    
    if not results or 'hits' not in results or len(results['hits']) == 0:
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
    
    user_data[user_id]['search_term'] = search_term
    user_data[user_id]['search_results'] = results['hits']
    user_data[user_id]['current_index'] = 0
    
    show_result(chat_id, user_id, message_id=user_data[user_id]['search_message_id'])

def check_subscription(user_id):
    """التحقق من اشتراك المستخدم في جميع القنوات المطلوبة"""
    not_subscribed = []
    for channel in REQUIRED_CHANNELS:
        try:
            chat_member = bot.get_chat_member(chat_id=channel, user_id=user_id)
            if chat_member.status not in ['member', 'administrator', 'creator']:
                not_subscribed.append(channel)
        except Exception as e:
            logger.error(f"خطأ في التحقق من الاشتراك في {channel}: {e}")
            not_subscribed.append(channel)
    return not_subscribed

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
    else:
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
    
    caption = f"{get_random_emoji()} **البحث:** {search_term}\n"
    caption += f"📊 **النتيجة {current_index+1} من {len(results)}**\n"
    if 'tags' in item:
        caption += f"🏷️ **الوسوم:** {item['tags']}\n"
    
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
    
    try:
        if 'videos' in item:
            video_url = item['videos']['medium']['url']
            
            if not is_valid_url(video_url):
                raise ValueError("رابط الفيديو غير صالح")
            
            if message_id:
                try:
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
                    user_data[user_id]['last_message_id'] = message_id
                    return
                except Exception as e:
                    logger.error(f"فشل في تعديل رسالة الفيديو: {e}")
            
            msg = bot.send_video(chat_id, video_url, caption=caption, reply_markup=markup, parse_mode='Markdown')
            user_data[user_id]['last_message_id'] = msg.message_id
        else:
            image_url = item.get('largeImageURL', item.get('webformatURL', ''))
            
            if not is_valid_url(image_url):
                raise ValueError("رابط الصورة غير صالح")
            
            if message_id:
                try:
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
                    user_data[user_id]['last_message_id'] = message_id
                    return
                except Exception as e:
                    logger.error(f"فشل في تعديل رسالة الصورة: {e}")
            
            msg = bot.send_photo(chat_id, image_url, caption=caption, reply_markup=markup, parse_mode='Markdown')
            user_data[user_id]['last_message_id'] = msg.message_id
    except Exception as e:
        logger.error(f"خطأ في عرض النتيجة: {e}")
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
    
    user_data[user_id]['last_interaction'] = datetime.now()
    
    not_subscribed = check_subscription(user_id)
    if not_subscribed:
        bot.answer_callback_query(call.id, "❗️ يجب الاشتراك في القنوات أولاً", show_alert=True)
        return
    
    if user_id not in user_data or 'search_results' not in user_data[user_id]:
        bot.answer_callback_query(call.id, "⏰ انتهت جلسة البحث، ابدأ بحثاً جديداً")
        return
    
    if action == 'prev':
        user_data[user_id]['current_index'] -= 1
    elif action == 'next':
        user_data[user_id]['current_index'] += 1
    
    user_data[user_id]['last_message_id'] = call.message.message_id
    show_result(chat_id, user_id, message_id=call.message.message_id)

@bot.callback_query_handler(func=lambda call: call.data == "download")
def download_content(call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    
    user_data[user_id]['last_interaction'] = datetime.now()
    
    not_subscribed = check_subscription(user_id)
    if not_subscribed:
        bot.answer_callback_query(call.id, "❗️ يجب الاشتراك في القنوات أولاً", show_alert=True)
        return
    
    try:
        bot.edit_message_reply_markup(
            chat_id=chat_id,
            message_id=call.message.message_id,
            reply_markup=None
        )
    except Exception as e:
        logger.error(f"خطأ في ازالة الازرار: {e}")
    
    bot.answer_callback_query(call.id, f"{get_random_emoji()} تم التحميل بنجاح!", show_alert=False)
    
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
{get_random_emoji()} **عن المطور** {ADMIN_USERNAME}

مطور مبتدئ في عالم بوتات تيليجرام، بدأ رحلته بشغف كبير لتعلم البرمجة وصناعة أدوات ذكية تساعد المستخدمين وتضيف قيمة للمجتمعات الرقمية. يسعى لتطوير مهاراته يومًا بعد يوم من خلال التجربة، التعلم، والمشاركة في مشاريع بسيطة لكنها فعالة.

**ما يميزه في هذه المرحلة:**
• حب الاستكشاف والتعلم الذاتي
• بناء بوتات بسيطة بمهام محددة
• استخدام أدوات مثل BotFather و Python
• الانفتاح على النقد والتطوير المستمر

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
        logger.error(f"خطأ في عرض معلومات المطور: {e}")

@bot.callback_query_handler(func=lambda call: call.data == "back_to_main")
def return_to_main(call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    show_main_menu(chat_id, user_id)

if __name__ == '__main__':
    logger.info("بدء تشغيل البوت...")
    start_periodic_tasks()
    set_webhook()
    app.run(host='0.0.0.0', port=10000)
