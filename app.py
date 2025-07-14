from flask import Flask, render_template, request, jsonify, send_file, session, redirect, url_for
from datetime import datetime, date, timedelta
import pandas as pd
from io import BytesIO
import json
import os
import logging

app = Flask(__name__)
app.secret_key = 'your_secure_secret_key_here_2025'

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 人员分组数据文件
GROUPS_FILE = 'groups_data.json'

# 默认人员分组数据
default_groups = [
    {"name": "多旋翼", "members": ["屈圣桥", "严梓睿", "桑振涛", "孙裔航", "张裕祥", "肖宇鹏", "郑天喆", "李勃均"]},
    {"name": "查打", "members": ["张欣童", "李勃均", "王熙哲", "付彻", "刘秋月", "龙天行", "牛子游", "屈圣桥"]},
    {"name": "微型固定翼", "members": ["居赞", "叶良来", "郭择明", "龚嘉文", "龙星儒", "张家鹤", "李文聪", "李延峰"]},
    {"name": "限时载运", "members": ["张家鹤", "居赞", "胡佳仪", "王思琪", "徐俊杰", "于浩弘", "孙彬皓", "迟赟之", "杨远哲", "尚孟轩"]},
    {"name": "机翼静载", "members": ["田之洞", "王思琪"]}
]


def load_groups():
    """加载分组数据"""
    if os.path.exists(GROUPS_FILE):
        try:
            with open(GROUPS_FILE, 'r', encoding='utf-8') as f:
                groups = json.load(f)
                logger.info("分组数据加载成功")
                return groups
        except Exception as e:
            logger.error(f"分组数据加载失败: {e}")
            return default_groups
    return default_groups


def save_groups(groups):
    """保存分组数据"""
    try:
        with open(GROUPS_FILE, 'w', encoding='utf-8') as f:
            json.dump(groups, f, ensure_ascii=False, indent=2)
        logger.info("分组数据保存成功")
    except Exception as e:
        logger.error(f"保存分组数据失败: {e}")
        raise


# 全局分组数据
groups = load_groups()

# 存储签到记录 - 使用文件持久化
DATA_FILE = 'attendance_data.json'
BACKUP_DIR = 'backups'


def ensure_backup_dir():
    """确保备份目录存在"""
    if not os.path.exists(BACKUP_DIR):
        os.makedirs(BACKUP_DIR)


def backup_data():
    """备份数据"""
    try:
        ensure_backup_dir()
        if os.path.exists(DATA_FILE):
            backup_filename = f"attendance_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            backup_path = os.path.join(BACKUP_DIR, backup_filename)

            with open(DATA_FILE, 'r', encoding='utf-8') as src:
                with open(backup_path, 'w', encoding='utf-8') as dst:
                    dst.write(src.read())

            logger.info(f"数据备份成功: {backup_path}")

            # 清理旧备份（保留最近10个）
            cleanup_old_backups()
    except Exception as e:
        logger.error(f"数据备份失败: {e}")


def cleanup_old_backups():
    """清理旧备份文件"""
    try:
        backup_files = []
        for filename in os.listdir(BACKUP_DIR):
            if filename.startswith('attendance_backup_') and filename.endswith('.json'):
                filepath = os.path.join(BACKUP_DIR, filename)
                backup_files.append((filepath, os.path.getmtime(filepath)))

        # 按修改时间排序，保留最新的10个
        backup_files.sort(key=lambda x: x[1], reverse=True)
        for filepath, _ in backup_files[10:]:
            os.remove(filepath)
            logger.info(f"清理旧备份: {filepath}")
    except Exception as e:
        logger.error(f"清理备份失败: {e}")


def load_data():
    """加载签到数据"""
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                logger.info("数据加载成功")
                return data
        except Exception as e:
            logger.error(f"数据加载失败: {e}")
            # 尝试从备份恢复
            return restore_from_backup()
    return {}


def restore_from_backup():
    """从备份恢复数据"""
    try:
        ensure_backup_dir()
        backup_files = []
        for filename in os.listdir(BACKUP_DIR):
            if filename.startswith('attendance_backup_') and filename.endswith('.json'):
                filepath = os.path.join(BACKUP_DIR, filename)
                backup_files.append((filepath, os.path.getmtime(filepath)))

        if backup_files:
            # 使用最新的备份
            latest_backup = max(backup_files, key=lambda x: x[1])[0]
            with open(latest_backup, 'r', encoding='utf-8') as f:
                data = json.load(f)
                logger.info(f"从备份恢复数据成功: {latest_backup}")
                return data
    except Exception as e:
        logger.error(f"从备份恢复数据失败: {e}")

    return {}


def save_data(data):
    """保存签到数据"""
    try:
        # 先备份现有数据
        if os.path.exists(DATA_FILE):
            backup_data()

        # 保存新数据
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info("数据保存成功")
    except Exception as e:
        logger.error(f"保存数据失败: {e}")
        raise


# 全局数据存储
attendance_records = load_data()

# 管理员凭据
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123"

# 用户签到密码
USER_PASSWORD = "dlut2025"


def get_today_date():
    """获取今天的日期字符串"""
    return date.today().isoformat()


def get_all_members():
    """获取所有成员列表（去重）"""
    all_members = set()
    for group in groups:
        for member in group["members"]:
            all_members.add(member)
    return sorted(list(all_members))


def get_today_records():
    """获取今天的签到记录"""
    today = get_today_date()
    if today not in attendance_records:
        attendance_records[today] = {}
        # 为所有成员初始化空记录
        for member in get_all_members():
            attendance_records[today][member] = []
        save_data(attendance_records)
    return attendance_records[today]


def get_date_records(date_str):
    """获取指定日期的签到记录"""
    return attendance_records.get(date_str, None)


def validate_time_format(time_str):
    """验证时间格式"""
    try:
        datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S")
        return True
    except ValueError:
        return False


def calculate_work_duration(sign_in, sign_out):
    """计算工作时长（秒）"""
    try:
        if not sign_in or not sign_out:
            return 0

        time_in = datetime.strptime(sign_in, "%Y-%m-%d %H:%M:%S")
        time_out = datetime.strptime(sign_out, "%Y-%m-%d %H:%M:%S")

        # 确保签退时间晚于签到时间
        if time_out <= time_in:
            return 0

        return (time_out - time_in).total_seconds()
    except Exception as e:
        logger.error(f"计算工作时长失败: {e}")
        return 0


def ensure_member_records(member_name):
    """确保新成员在所有日期的记录中都有空记录"""
    for date_str in attendance_records:
        if member_name not in attendance_records[date_str]:
            attendance_records[date_str][member_name] = []


def cleanup_member_records(member_name):
    """清理已删除成员的记录（可选，保留历史数据）"""
    # 这里我们选择保留历史数据，不删除记录
    # 如果需要删除，可以取消注释以下代码：
    # for date_str in attendance_records:
    #     if member_name in attendance_records[date_str]:
    #         del attendance_records[date_str][member_name]
    pass


@app.route('/')
def index():
    """主页 - 检查用户登录状态"""
    user_logged_in = session.get('user_logged_in', False)
    admin_logged_in = session.get('admin_logged_in', False)

    # 如果用户未登录，重定向到用户登录页面
    if not user_logged_in and not admin_logged_in:
        return redirect(url_for('user_login'))

    # 获取所有成员
    all_members = get_all_members()
    total_people = len(all_members)

    # 获取今天的记录
    today_records = get_today_records()

    # 计算签到状态
    signed_in_count = 0
    signed_out_count = 0
    not_signed_count = 0

    for member in all_members:
        records = today_records.get(member, [])
        if records:
            last_record = records[-1]
            if last_record.get('sign_out'):
                signed_out_count += 1
            else:
                signed_in_count += 1
        else:
            not_signed_count += 1

    return render_template(
        'index.html',
        groups=groups,
        admin=admin_logged_in,
        user_logged_in=user_logged_in,
        total_people=total_people,
        signed_in_count=signed_in_count,
        signed_out_count=signed_out_count,
        not_signed_count=not_signed_count
    )


@app.route('/user_login', methods=['GET', 'POST'])
def user_login():
    """用户登录页面"""
    if request.method == 'POST':
        password = request.form.get('password', '').strip()

        if password == USER_PASSWORD:
            session['user_logged_in'] = True
            session.permanent = True
            logger.info("用户登录成功")
            return redirect(url_for('index'))
        else:
            logger.warning("用户登录失败")
            return render_template('user_login.html', error="密码错误，请重试")

    return render_template('user_login.html', error=None)


@app.route('/admin_login', methods=['GET', 'POST'])
def admin_login():
    """管理员登录页面"""
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()

        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session['admin_logged_in'] = True
            session['user_logged_in'] = True  # 管理员也有用户权限
            session.permanent = True
            logger.info("管理员登录成功")
            return redirect(url_for('index'))
        else:
            logger.warning(f"管理员登录失败: {username}")
            return render_template('admin_login.html', error="用户名或密码错误")

    return render_template('admin_login.html', error=None)


@app.route('/logout')
def logout():
    """登出"""
    session.pop('admin_logged_in', None)
    session.pop('user_logged_in', None)
    logger.info("用户登出")
    return redirect(url_for('user_login'))


@app.route('/sign', methods=['POST'])
def sign():
    """处理签到/签退"""
    # 检查用户登录状态
    if not session.get('user_logged_in', False) and not session.get('admin_logged_in', False):
        return jsonify({"status": "error", "message": "请先登录"})

    try:
        name = request.form.get('name', '').strip()
        if not name:
            return jsonify({"status": "error", "message": "未提供姓名"})

        # 检查姓名是否在成员列表中
        all_members = get_all_members()
        if name not in all_members:
            return jsonify({"status": "error", "message": "无效的姓名"})

        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        today_records = get_today_records()

        records = today_records.get(name, [])
        action = ""

        # 如果没有记录或最后一条记录已签退，则签到
        if not records or (records and records[-1].get('sign_out')):
            new_record = {"sign_in": current_time, "sign_out": None}
            records.append(new_record)
            action = "sign_in"
            logger.info(f"{name} 签到成功: {current_time}")
        # 如果最后一条记录未签退，则签退
        else:
            records[-1]["sign_out"] = current_time
            action = "sign_out"
            logger.info(f"{name} 签退成功: {current_time}")

        today_records[name] = records
        attendance_records[get_today_date()] = today_records
        save_data(attendance_records)

        return jsonify({
            "status": "success",
            "action": action,
            "time": current_time,
            "name": name
        })

    except Exception as e:
        logger.error(f"签到处理错误: {e}")
        return jsonify({"status": "error", "message": "服务器错误，请重试"})


@app.route('/get_attendance')
def get_attendance():
    """获取今天的签到记录"""
    # 检查用户登录状态
    if not session.get('user_logged_in', False) and not session.get('admin_logged_in', False):
        return jsonify({"error": "请先登录"}), 403

    try:
        return jsonify(get_today_records())
    except Exception as e:
        logger.error(f"获取签到记录错误: {e}")
        return jsonify({})


@app.route('/get_history_attendance/<date_str>')
def get_history_attendance(date_str):
    """获取历史签到记录"""
    if not session.get('admin_logged_in', False):
        return jsonify({"error": "需要管理员权限"}), 403

    try:
        # 验证日期格式
        datetime.strptime(date_str, '%Y-%m-%d')

        records = get_date_records(date_str)
        if records is None:
            return jsonify({"error": "没有找到该日期的记录"}), 404
        return jsonify(records)
    except ValueError:
        return jsonify({"error": "日期格式错误"}), 400
    except Exception as e:
        logger.error(f"获取历史记录错误: {e}")
        return jsonify({"error": "服务器错误"}), 500


# 新增：成员管理API
@app.route('/api/groups', methods=['GET'])
def get_groups():
    """获取所有分组信息"""
    if not session.get('admin_logged_in', False):
        return jsonify({"error": "需要管理员权限"}), 403

    return jsonify(groups)


@app.route('/api/groups', methods=['POST'])
def update_groups():
    """更新分组信息"""
    if not session.get('admin_logged_in', False):
        return jsonify({"error": "需要管理员权限"}), 403

    try:
        global groups
        new_groups = request.json

        # 验证数据格式
        if not isinstance(new_groups, list):
            return jsonify({"error": "数据格式错误"}), 400

        for group in new_groups:
            if not isinstance(group, dict) or 'name' not in group or 'members' not in group:
                return jsonify({"error": "分组数据格式错误"}), 400
            if not isinstance(group['members'], list):
                return jsonify({"error": "成员列表格式错误"}), 400

        # 获取新的成员列表
        old_members = set(get_all_members())
        groups = new_groups
        new_members = set(get_all_members())

        # 为新成员创建记录
        added_members = new_members - old_members
        for member in added_members:
            ensure_member_records(member)

        # 清理已删除成员的记录（可选）
        removed_members = old_members - new_members
        for member in removed_members:
            cleanup_member_records(member)

        # 保存分组数据
        save_groups(groups)

        # 保存签到数据
        save_data(attendance_records)

        logger.info(f"分组数据更新成功，新增成员: {added_members}, 移除成员: {removed_members}")

        return jsonify({
            "status": "success",
            "message": "分组数据更新成功",
            "added_members": list(added_members),
            "removed_members": list(removed_members)
        })

    except Exception as e:
        logger.error(f"更新分组数据失败: {e}")
        return jsonify({"error": "更新失败"}), 500


@app.route('/api/groups/<group_name>/members', methods=['POST'])
def add_member_to_group(group_name):
    """向指定分组添加成员"""
    if not session.get('admin_logged_in', False):
        return jsonify({"error": "需要管理员权限"}), 403

    try:
        data = request.json
        member_name = data.get('name', '').strip()

        if not member_name:
            return jsonify({"error": "成员姓名不能为空"}), 400

        # 查找分组
        group_found = False
        for group in groups:
            if group['name'] == group_name:
                if member_name not in group['members']:
                    group['members'].append(member_name)
                    ensure_member_records(member_name)
                    group_found = True
                    break
                else:
                    return jsonify({"error": "成员已存在"}), 400

        if not group_found:
            return jsonify({"error": "分组不存在"}), 404

        # 保存数据
        save_groups(groups)
        save_data(attendance_records)

        logger.info(f"成员 {member_name} 添加到分组 {group_name}")
        return jsonify({"status": "success", "message": "成员添加成功"})

    except Exception as e:
        logger.error(f"添加成员失败: {e}")
        return jsonify({"error": "添加失败"}), 500


@app.route('/api/groups/<group_name>/members/<member_name>', methods=['DELETE'])
def remove_member_from_group(group_name, member_name):
    """从指定分组移除成员"""
    if not session.get('admin_logged_in', False):
        return jsonify({"error": "需要管理员权限"}), 403

    try:
        # 查找并移除成员
        group_found = False
        member_found = False

        for group in groups:
            if group['name'] == group_name:
                group_found = True
                if member_name in group['members']:
                    group['members'].remove(member_name)
                    member_found = True
                    break

        if not group_found:
            return jsonify({"error": "分组不存在"}), 404

        if not member_found:
            return jsonify({"error": "成员不存在"}), 404

        # 检查成员是否在其他分组中
        member_in_other_groups = False
        for group in groups:
            if member_name in group['members']:
                member_in_other_groups = True
                break

        # 如果成员不在任何分组中，清理记录
        if not member_in_other_groups:
            cleanup_member_records(member_name)

        # 保存数据
        save_groups(groups)
        save_data(attendance_records)

        logger.info(f"成员 {member_name} 从分组 {group_name} 移除")
        return jsonify({"status": "success", "message": "成员移除成功"})

    except Exception as e:
        logger.error(f"移除成员失败: {e}")
        return jsonify({"error": "移除失败"}), 500


@app.route('/export')
def export():
    """导出今日报表"""
    return export_date(get_today_date())


@app.route('/export/<date_str>')
def export_date(date_str):
    """导出指定日期的报表"""
    if not session.get('admin_logged_in', False):
        return redirect(url_for('admin_login'))

    try:
        # 验证日期格式
        datetime.strptime(date_str, '%Y-%m-%d')

        records = get_date_records(date_str)
        if records is None:
            return "没有找到该日期的记录", 404

        output = BytesIO()

        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            # 汇总表
            summary_data = []
            for group in groups:
                for name in group["members"]:
                    person_records = records.get(name, [])
                    total_seconds = 0
                    valid_sessions = 0

                    for record in person_records:
                        duration = calculate_work_duration(
                            record.get('sign_in'),
                            record.get('sign_out')
                        )
                        if duration > 0:
                            total_seconds += duration
                            valid_sessions += 1

                    hours = int(total_seconds // 3600)
                    minutes = int((total_seconds % 3600) // 60)
                    total_time = f"{hours}小时{minutes}分钟" if total_seconds > 0 else "0小时0分钟"

                    summary_data.append({
                        "组别": group["name"],
                        "姓名": name,
                        "有效签到次数": valid_sessions,
                        "总签到次数": len(person_records),
                        "总工作时长": total_time,
                        "工作时长(小时)": round(total_seconds / 3600, 2)
                    })

            df_summary = pd.DataFrame(summary_data)
            df_summary.to_excel(writer, sheet_name="汇总", index=False)

            # 详细记录表
            for group in groups:
                group_data = []
                for name in group["members"]:
                    person_records = records.get(name, [])
                    for i, record in enumerate(person_records, 1):
                        sign_in = record.get('sign_in', '')
                        sign_out = record.get('sign_out', '')
                        duration = ""
                        status = "未完成"

                        if sign_in and sign_out:
                            duration_seconds = calculate_work_duration(sign_in, sign_out)
                            if duration_seconds > 0:
                                hours = int(duration_seconds // 3600)
                                minutes = int((duration_seconds % 3600) // 60)
                                duration = f"{hours}小时{minutes}分钟"
                                status = "已完成"
                            else:
                                duration = "时间异常"
                                status = "异常"
                        elif sign_in:
                            status = "进行中"

                        group_data.append({
                            "姓名": name,
                            "序号": i,
                            "签到时间": sign_in,
                            "签退时间": sign_out,
                            "工作时长": duration,
                            "状态": status
                        })

                df = pd.DataFrame(group_data)
                sheet_name = group["name"][:30]  # 限制sheet名称长度
                if df.empty:
                    df = pd.DataFrame({"提示": [f"{sheet_name}无签到记录"]})

                df.to_excel(writer, sheet_name=sheet_name, index=False)

        output.seek(0)
        logger.info(f"导出报表成功: {date_str}")
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=f"签到记录_{date_str}.xlsx"
        )

    except ValueError:
        return "日期格式错误", 400
    except Exception as e:
        logger.error(f"导出错误: {e}")
        return "导出失败", 500


@app.route('/get_available_dates')
def get_available_dates():
    """获取可用的历史日期"""
    if not session.get('admin_logged_in', False):
        return jsonify({"error": "需要管理员权限"}), 403

    try:
        dates = list(attendance_records.keys())
        dates.sort(reverse=True)
        return jsonify(dates)
    except Exception as e:
        logger.error(f"获取日期列表错误: {e}")
        return jsonify([])


@app.route('/timeline')
def timeline():
    """工作时长示意图页面"""
    # 检查用户登录状态
    if not session.get('user_logged_in', False) and not session.get('admin_logged_in', False):
        return redirect(url_for('user_login'))

    today = get_today_date()
    records = get_today_records()

    # 计算每个人的工作时间段
    work_periods = {}
    for name in get_all_members():
        periods = []
        entries = records.get(name, [])

        for entry in entries:
            if entry.get('sign_in') and entry.get('sign_out'):
                try:
                    sign_in = datetime.strptime(entry['sign_in'], "%Y-%m-%d %H:%M:%S")
                    sign_out = datetime.strptime(entry['sign_out'], "%Y-%m-%d %H:%M:%S")

                    # 确保时间有效
                    if sign_out > sign_in:
                        # 计算工作时间段（小时）
                        start_hour = sign_in.hour + sign_in.minute / 60 + sign_in.second / 3600
                        end_hour = sign_out.hour + sign_out.minute / 60 + sign_out.second / 3600

                        # 处理跨天情况
                        if sign_out.date() > sign_in.date():
                            end_hour += 24

                        # 确保时间段在合理范围内
                        if 0 <= start_hour < 48 and 0 <= end_hour < 48 and end_hour > start_hour:
                            periods.append({
                                'start': start_hour,
                                'end': end_hour,
                                'duration': end_hour - start_hour,
                                'sign_in_time': entry['sign_in'],
                                'sign_out_time': entry['sign_out']
                            })
                except Exception as e:
                    logger.error(f"处理时间段失败 {name}: {e}")
                    continue

        work_periods[name] = periods

    return render_template(
        'timeline.html',
        groups=groups,
        work_periods=work_periods,
        today=today
    )


@app.route('/api/stats')
def get_stats():
    """获取统计信息API"""
    # 检查用户登录状态
    if not session.get('user_logged_in', False) and not session.get('admin_logged_in', False):
        return jsonify({"error": "请先登录"}), 403

    try:
        today_records = get_today_records()
        all_members = get_all_members()

        stats = {
            'total_members': len(all_members),
            'signed_in': 0,
            'signed_out': 0,
            'not_signed': 0,
            'total_work_hours': 0,
            'active_sessions': 0
        }

        for member in all_members:
            records = today_records.get(member, [])
            if records:
                last_record = records[-1]
                if last_record.get('sign_out'):
                    stats['signed_out'] += 1
                else:
                    stats['signed_in'] += 1
                    stats['active_sessions'] += 1

                # 计算总工作时长
                for record in records:
                    duration = calculate_work_duration(
                        record.get('sign_in'),
                        record.get('sign_out')
                    )
                    stats['total_work_hours'] += duration / 3600
            else:
                stats['not_signed'] += 1

        stats['total_work_hours'] = round(stats['total_work_hours'], 2)
        return jsonify(stats)

    except Exception as e:
        logger.error(f"获取统计信息失败: {e}")
        return jsonify({"error": "获取统计信息失败"}), 500


@app.errorhandler(404)
def not_found_error(error):
    return render_template('404.html'), 404


@app.errorhandler(500)
def internal_error(error):
    logger.error(f"内部服务器错误: {error}")
    return render_template('500.html'), 500

@app.after_request
def add_header(r):
    """
    Add headers to both force latest IE rendering engine or Chrome Frame,
    and also to cache the rendered page for 10 minutes.
    """
    r.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    r.headers["Pragma"] = "no-cache"
    r.headers["Expires"] = "0"
    r.headers['Cache-Control'] = 'public, max-age=0'
    return r

if __name__ == '__main__':
    print("=" * 50)
    print("启动签到系统...")
    print(f"管理员账号: {ADMIN_USERNAME}")
    print(f"管理员密码: {ADMIN_PASSWORD}")
    print(f"用户签到密码: {USER_PASSWORD}")
    print("访问地址: http://localhost:5001")
    print("时间线页面: http://localhost:5001/timeline")
    print("=" * 50)

    # 确保备份目录存在
    ensure_backup_dir()

    app.run(debug=True, host='0.0.0.0', port=5001)