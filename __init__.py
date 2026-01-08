from zfn_api import Client
import base64
import os
import sys
import traceback
from pprint import pprint
import time
from datetime import datetime
import pytz

username="学号"
password="密码"


def get_beijing_time():
    beijing_tz = pytz.timezone('Asia/Shanghai')
    return datetime.now(beijing_tz)

def get_year_and_quarter():
    beijing_tz = pytz.timezone('Asia/Shanghai')
    current_time = datetime.now(beijing_tz)
    current_month = current_time.month
    
    if current_month >= 11:
        return current_time.year, 1
    elif current_month <= 4:
        return current_time.year - 1, 1
    else:
        return current_time.year, 2

cookies = {}
base_url = "https://jwglxxfwpt.hebeu.edu.cn"  # 此处填写教务系统URL
raspisanie = []
ignore_type = []
detail_category_type = []
timeout = 5

stu = Client(cookies=cookies, base_url=base_url, raspisanie=raspisanie, ignore_type=ignore_type, detail_category_type=detail_category_type, timeout=timeout)

student_client = stu

if cookies == {}:
    lgn = stu.login(username, password)  # 此处填写账号及密码
    
    if lgn["code"] == 1001:
        verify_data = lgn["data"]
        with open(os.path.abspath("kaptcha.png"), "wb") as pic:
            pic.write(base64.b64decode(verify_data.pop("kaptcha_pic")))
        verify_data["kaptcha"] = input("输入验证码：")
        ret = stu.login_with_kaptcha(**verify_data)
        if ret["code"] != 1000:
            pprint(ret)
            sys.exit()
        pprint(ret)
    elif lgn["code"] != 1000:
        pprint(lgn)
        sys.exit()

def get_selected_courses(student_client):
    try:
        # 获取成绩信息
        grade = get_grade(student_client, output_type="grade")

        # 定义重试次数上限为5次
        attempts = 5
        # 初始化selected_courses为空列表
        selected_courses = []

        # 使用while循环最多重试5次获取已选课程信息
        while attempts > 0:
            # 调用student_client的get_selected_courses方法获取已选课程信息
            selected_courses_data = student_client.get_selected_courses().get("data", {})
            selected_courses = selected_courses_data.get("courses", [])

            # 如果selected_courses不为空，跳出循环
            if selected_courses:
                break

            # 如果selected_courses为空，等待1秒后重试
            time.sleep(1)
            # 减少剩余重试次数
            attempts -= 1

        # 已选课程信息不为空时,处理未公布成绩的课程
        if selected_courses:
            # 按照学年学期降序排序
            # 对于没有学年学期参数的课程，则将学年学期设置为1970至1971学年第1学期，否则将无法排序
            selected_courses = sorted(
                selected_courses,
                key=lambda x: (
                    (x["course_year"] if x["course_year"] else "1970-1971"),
                    (x["course_semester"] if x["course_semester"] else "1"),
                ),
                reverse=True,
            )

            # 初始化空字典用于存储未公布成绩的课程,按学年学期分组
            ungraded_courses_by_semester = {}

            # 获取成绩列表中的class_id集合
            grade_class_ids = {course["class_id"] for course in grade} if grade else ""

            # 初始化输出内容
            selected_courses_filtering = ""

            # 遍历selected_courses和grade中的每个课程
            for course in selected_courses + (grade or []):
                # 获取课程的学年和学期
                try:
                    year, semester, seq = course["course_year"].split("-") + [course["course_semester"]]
                except Exception:
                    pass

                # 构建年学期名称,例如 "a至b学年第c学期"
                yearsemester_name = f"{year}至{semester}学年第{seq}学期"

                # 判断课程是否未公布成绩
                if course["class_id"] not in grade_class_ids:
                    # 未公布成绩
                    ungraded_courses_by_semester.setdefault(yearsemester_name, []).append(f"{course['title'].replace('（', '(').replace('）', ')')} - {course['teacher']}")

            # 构建输出内容
            if ungraded_courses_by_semester:
                # 存在未公布成绩的课程
                selected_courses_filtering += "------\n未公布成绩的课程："
                for i, (semester, courses) in enumerate(ungraded_courses_by_semester.items()):
                    if i > 0:
                        selected_courses_filtering += "\n------"
                    selected_courses_filtering += f"\n{semester}："
                    for course in courses:
                        selected_courses_filtering += f"\n{course}"
        else:
            selected_courses_filtering = "------\n未公布成绩的课程：\n已选课程信息为空"
        return selected_courses_filtering

    except Exception:
        print(traceback.format_exc())
        return "------\n未公布成绩的课程：\n获取未公布成绩的课程时出错"


def get_user_info(student_client, output_type="none"):
    try:
        # 定义重试次数上限为5次
        attempts = 5
        # 初始化info为空字典
        info = {}

        # 使用while循环最多重试5次获取个人信息
        while attempts > 0:
            # 调用student_client的get_info方法获取个人信息字典
            info = student_client.get_info().get("data", {})

            # 如果info不为空，退出循环
            if info:
                break

            # 如果info为空，等待1秒后重试
            time.sleep(1)
            # 减少剩余重试次数
            attempts -= 1

        # 如果成功获取到个人信息
        if info:
            # 整合个人信息为字符串格式
            info = (
                f"个人信息：\n"
                f"学号：{info['sid']}\n"
                f"班级：{info['class_name']}\n"
                f"姓名：{info['name']}"
            )

            # 调用get_grade方法获取学生成绩信息
            grade = get_grade(student_client, output_type="grade")

            # 如果成功获取到成绩信息
            if grade:
                # 获取当前GPA
                gpa = get_grade(student_client, output_type="gpa")
                # 获取当前百分制GPA
                percentage_gpa = get_grade(student_client, output_type="percentage_gpa")
                # 整合GPA信息为字符串格式
                gpa_info = f"\n当前GPA：{gpa}\n" f"当前百分制GPA：{percentage_gpa}\n此项结果使用[(学分*绩点)的总和/学分总和]计算而来\n与学校学生学业情况的绩点存在差异\n请以学生学业情况为准"
                # 将个人信息和GPA信息整合为完整字符串
                integrated_info = f"{info}{gpa_info}"

                # 根据output_type返回不同类型的信息
                if output_type == "info":
                    return info
                elif output_type == "integrated_info":
                    return integrated_info
                else:
                    # 如果output_type参数无效，返回错误提示
                    return "获取个人信息：参数缺失"
            else:
                # 如果未获取到成绩信息，返回仅包含个人信息的字符串
                return f"{info}"

    except Exception:
        # 捕获并打印所有异常的详细信息
        print(traceback.format_exc())
        # 返回错误提示信息
        return "个人信息：\n获取个人信息时出错"



def get_grade(student_client, output_type="none"):
    try:
        # 定义重试次数上限为5次
        attempts = 5
        # 初始化grade为空列表
        grade = []

        # 使用while循环最多重试5次获取成绩信息
        while attempts > 0:

            # 调用student_client的get_grade方法获取成绩信息
            grade_data = student_client.get_grade().get("data", {})
            grade = grade_data.get("courses", [])

            # 如果grade不为空，跳出循环
            if grade:
                break

            # 如果grade为空，等待1秒后重试
            time.sleep(1)
            # 减少剩余重试次数
            attempts -= 1

        # 成绩不为空时
        if grade:
            # 过滤出成绩大于等于60分的课程
            filtered_grade = list(filter(lambda x: float(x["percentage_grades"]) >= 60, grade))
            

            # 遍历 grade 中的每个字典，将 title 中的中文括号替换为英文括号
            for course_data_grade in grade:
                course_data_grade["title"] = (
                    course_data_grade["title"].replace("（", "(").replace("）", ")")
                )

            # 按照提交时间降序排序
            # 对于没有提交时间参数的成绩，则将提交时间设置为1970-01-01 00:00:00，否则将无法排序
            sorted_grade = sorted(
                grade,
                key=lambda x: (
                    x["submission_time"] if x["submission_time"] else "1970-01-01 00:00:00"
                ),
                reverse=True,
            )

            # 大于等于60分的课程不为空时
            if filtered_grade:
                # 学分总和
                total_credit = sum(float(course["credit"]) for course in filtered_grade)

                # 学分绩点总和
                total_xfjd = sum(float(course["xfjd"]) for course in filtered_grade)

                # (百分制成绩*学分)的总和
                sum_of_percentage_grades_multiplied_by_credits = sum(
                    float(course["percentage_grades"]) * float(course["credit"])
                    for course in filtered_grade
                )

                # GPA计算 (学分*绩点)的总和/学分总和
                gpa = "{:.2f}".format(total_xfjd / total_credit)

                # 百分制GPA计算 (百分制成绩*学分)的总和/学分总和
                percentage_gpa = "{:.2f}".format(
                    sum_of_percentage_grades_multiplied_by_credits / total_credit
                )
            else:
                total_credit = total_xfjd = sum_of_percentage_grades_multiplied_by_credits = gpa = (
                    percentage_gpa
                ) = 0

            # 初始化输出成绩信息字符串
            integrated_grade_info = "------\n成绩信息："

            # 遍历前8条成绩信息
            for _, course in enumerate(sorted_grade[:]):

                # 如果成绩非数字，如及格、良好、中等、优秀等，则显示百分制成绩
                if str(course["grade"]).isdigit():
                    score_grades = course["grade"]
                else:
                    score_grades = f"{course['grade']} ({course['percentage_grades']})"

                # 整合成绩信息
                integrated_grade_info += (
                    f"\n"
                    f"教学班ID：{course['class_id']}\n"
                    f"课程名称：{course['title']}\n"
                    f"任课教师：{course['teacher']}\n"
                    f"成绩：{score_grades}\n"
                    f"提交时间：{course['submission_time']}\n"
                    f"提交人姓名：{course['name_of_submitter']}\n"
                    f"------"
                )

            last_submission_time = sorted_grade[0]["submission_time"]

            if output_type == "grade":
                return grade
            elif output_type == "gpa":
                return gpa
            elif output_type == "percentage_gpa":
                return percentage_gpa
            elif output_type == "integrated_grade_info":
                return integrated_grade_info
            elif output_type == "last_submission_time":
                return last_submission_time
            else:
                return "获取成绩：参数缺失"

    except Exception:
        print(traceback.format_exc())
        return "获取成绩时出错"


year_use, quarter_use = get_year_and_quarter()

# 返回直接字符串

result = stu.get_info()  # 获取个人全部信息
# result = stu.get_grade(year_use, quarter_use)  # 获取成绩信息，若接口错误请添加 use_personal_info=True，只填年份获取全年
# result = stu.get_exam_schedule(year_use, quarter_use)  # 获取考试日程信息，只填年份获取全年
# result = stu.get_schedule(year_use, quarter_use)  # 获取课程表信息
# result = stu.get_academia()  # 获取学业生涯数据
# result = stu.get_notifications()  # 获取通知消息
# result = stu.get_selected_courses(year_use, quarter_use)  # 获取已选课程信息
pprint(result, sort_dicts=False)


# 此处以下为md格式，需要构建字符串
error_content = []


# 获取个人信息
integrated_info = get_user_info(stu, output_type="integrated_info")
print("\n=== 综合信息 ===\n")
print(integrated_info)

# # 获取学业情况
# gpa_data_all = stu.get_academia()
# if gpa_data_all["code"] == 1000:
#     print("\n=== 学业情况 ===\n")
#     print(gpa_data_all["data"]["statistics"])
# else:
#     print(f"\n获取学业情况失败: {gpa_data_all['msg']}")

# # 获取成绩
# try:
#     grade = get_grade(stu, output_type="grade")
#     print("\n=== 成绩信息 ===\n")
#     print(grade)
    
#     # 获取未公布成绩的课程
#     ungraded_courses = get_selected_courses(stu)
#     print("\n=== 未公布成绩的课程 ===\n")
#     print(ungraded_courses)
# except Exception as e:
#     print(f"\n获取成绩时出错: {str(e)}")
