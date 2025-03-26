import time
import sys
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QMainWindow, QApplication, QStyleFactory
from PyQt6.QtCore import QThread, pyqtSignal, pyqtSlot
from tool import Ui_Form  # 导入 UI 类
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


# 处理弹窗
def handle_popup_if_present(driver):
    try:
        WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, 'div.el-message-box__wrapper'))
        )
        confirm_button = driver.find_element(By.CSS_SELECTOR, 'div.el-message-box__btns .el-button--primary')
        confirm_button.click()
        print("弹窗出现，已自动点击")
    except Exception:
        print("没有发现弹窗")


# 检查视频是否播放完毕
def check_video_status(driver):
    try:
        video_player_div = driver.find_element(By.CSS_SELECTOR, 'div.video-player.video-player.vjs-custom-skin')
        first_child_div = video_player_div.find_element(By.XPATH, './div[1]')
        class_name = first_child_div.get_attribute('class')
        if 'vjs-ended' in class_name:
            return True
        elif 'vjs-playing' in class_name or 'vjs-user-active' in class_name:
            return False
        else:
            print("视频状态未知")
            return False
    except Exception as e:
        print(f"检查视频状态时出错: {e}")
        return False


# 线程 登录
class LoginThread(QThread):
    login_finished = pyqtSignal(str)
    driver_ready = pyqtSignal(object)

    def __init__(self, username, password):
        super().__init__()
        self.username = username
        self.password = password

    def run(self):
        # 检查用户名和密码是否为空
        if not self.username or not self.password:
            self.login_finished.emit("用户名或密码不能为空，请检查输入")
            return
        try:
            self.login_finished.emit("正在登录......初次启动预计需要10秒，请耐心等待，不要重复点击")
            options = Options()
            options.add_argument("--headless")  # 无头模式
            options.add_argument("--mute-audio")  # 禁用音频
            driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
            login_url = "https://jsjxjypt.com/login?redirect=%2F"
            driver.get(login_url)

            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'input[placeholder="账号"]'))
            )
            username_field = driver.find_element(By.CSS_SELECTOR, 'input[placeholder="账号"]')
            username_field.send_keys(self.username)
            password_field = driver.find_element(By.CSS_SELECTOR, 'input[placeholder="密码"]')
            password_field.send_keys(self.password)
            login_button = driver.find_element(By.CSS_SELECTOR, 'button.el-button--primary')
            login_button.click()
            WebDriverWait(driver, 10).until(EC.url_changes(login_url))
            self.login_finished.emit("登录成功")
            self.driver_ready.emit(driver)
        except Exception as e:
            self.login_finished.emit("登录失败，请检查账号密码是否有误")


# 线程 开始学习
class LearningThread(QThread):
    log_signal = pyqtSignal(str)  # 定义信号，用于更新日志

    def __init__(self, driver):
        super().__init__()
        self.driver = driver

    def run(self):
        try:
            # 学习所有的课程
            index = 0

            while True:
                # 每次开始循环前重新获取课程列表，防止元素失效
                divs_with_info = self.get_divs()

                # 检查是否有剩余课程需要学习
                if index >= len(divs_with_info):
                    break  # 如果没有更多课程，退出循环

                # 展示各个课程目前学习进度
                log_message = "您当前学习的课程列表：\n"
                for idx, (learned_minutes, course_name, progress_percentage, _) in enumerate(divs_with_info):
                    log_message += f"第 {idx + 1} 个课程：{course_name}，已学习 {learned_minutes} 分钟，完成度{progress_percentage}% \n"
                self.log_signal.emit(log_message)

                try:
                    learned_minutes, course_name, progress_percentage, div = divs_with_info[index]

                    # 展示学习总进度
                    self.show_progress(divs_with_info)

                    # 元素初始化
                    print(f"即将开始学习第 {index + 1} 个课程: {course_name}，正在加载主页内容...")

                    # 显式等待，确保 div 元素可见
                    WebDriverWait(self.driver, 10).until(
                        EC.visibility_of(div)
                    )

                    print("主页内容加载完毕")
                    self.log_signal.emit("主页内容加载完毕")

                    # 在当前 div 中寻找 去学习 按钮
                    learn_button = WebDriverWait(div, 10).until(
                        EC.element_to_be_clickable(
                            (By.XPATH, ".//button[span[text()='去学习']]")  # 使用相对 XPath，限制在当前 div 中查找
                        )
                    )

                    self.log_signal.emit("去学习按钮加载完毕")
                    print("去学习按钮加载完毕")

                    learn_button.click()
                    self.log_signal.emit("点击去学习按钮，正在跳转...")

                    # 弹窗处理
                    handle_popup_if_present(self.driver)

                    # 页面跳转
                    time.sleep(2)
                    WebDriverWait(self.driver, 10).until(EC.number_of_windows_to_be(2))
                    self.driver.switch_to.window(self.driver.window_handles[1])
                    self.log_signal.emit(f"{course_name}页面跳转成功")

                    try:
                        # 获取子页面视频列表
                        ul_elements, li_texts = self.get_videos()

                        # 播放课程内的子视频
                        self.switch_videos(ul_elements, li_texts)

                    except Exception as e:
                        print(f"在播放子视频时出错: {e}")
                        self.log_signal.emit(f"在播放子视频时出错，请检查网络状态或重启软件")

                    # 关闭当前页面并回到主页面
                    self.driver.close()
                    self.driver.switch_to.window(self.driver.window_handles[0])
                    # 刷新主窗口以获取最新课程列表
                    self.driver.refresh()
                    time.sleep(2)  # 等待页面加载

                except Exception as e:
                    print(f"处理第 {index + 1} 个课程时出错: {e}")

                # 处理完当前课程后，进入下一个课程
                index += 1

            self.log_signal.emit("所有课程学习完成")
            print("所有课程学习完成")

        except Exception as e:
            print(f"{e}")

    # 展示学习进度
    def show_progress(self, divs):
        # 展示学习总进度
        target_element = WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR,
                                            '#app > div > div > div > div:nth-child(3) > section > div > div > div.khyqWrap.kcxx_list > div:nth-child(2) > div:nth-child(2) > div:nth-child(2) > div > div > div > div > div'))
        )
        # 等待页面状态稳定
        time.sleep(2)
        element_text = target_element.text
        print(f"当前总学习进度：{element_text}")
        self.log_signal.emit(f"当前总学习进度：{element_text}")

    # 获取视频列表
    def get_videos(self):
        # 获取子页面视频列表
        WebDriverWait(self.driver, 10).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, 'ul[data-v-7cde8ccc]'))
        )
        ul_elements = self.driver.find_elements(By.CSS_SELECTOR, 'ul[data-v-7cde8ccc]')
        li_texts = []
        for ul in ul_elements:
            li_elements = ul.find_elements(By.CSS_SELECTOR, 'li')
            for li in li_elements:
                li_texts.append(li.text)
        self.log_signal.emit(f"当前课程视频列表:{li_texts}")
        return ul_elements, li_texts  # 返回两个值

    # 获取课程列表
    def get_divs(self):
        WebDriverWait(self.driver, 10).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, 'div.list'))
        )
        list_divs = self.driver.find_elements(By.CSS_SELECTOR, 'div.list')
        divs_with_info = []

        for div in list_divs:
            try:
                # 获取学习时间
                time_element = div.find_element(By.CSS_SELECTOR, 'p.xk_rs.clear > span.fl')
                time_text = time_element.text
                learned_minutes = int(time_text.replace("已学习 ", "").replace("分钟", ""))

                # 获取课程名称
                course_name_element = div.find_element(By.CSS_SELECTOR, 'p.kcal_title')
                course_name = course_name_element.text

                # 获取进度条百分比
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_all_elements_located((By.CSS_SELECTOR, 'div.el-progress-bar__innerText'))
                )
                progress_element = div.find_element(By.CSS_SELECTOR, 'div.el-progress-bar__innerText')
                progress_text = progress_element.text
                progress_percentage = int(progress_text.replace("%", ""))  # 将百分比转换为整数

                # 过滤已完成课程（进度 >= 100%）
                if progress_percentage >= 100:
                    continue

                # 将学习时间、课程名称、进度条百分比以及 div 元素添加到列表中
                divs_with_info.append((learned_minutes, course_name, progress_percentage, div))
            except Exception as e:
                print(f"在提取学习时间、课程名称或进度百分比时出错: {e}")
                continue

        # 按照 progress_percentage 从低到高进行排序
        divs_with_info.sort(key=lambda x: x[2])  # x[2] 是 progress_percentage
        return divs_with_info

    # 自动播放视频
    def switch_videos(self, ul_elements, li_texts):
        for index, ul in enumerate(ul_elements):
            try:
                # 使用 WebDriverWait 等待 ul 中的 li 元素出现后点击它
                li = WebDriverWait(ul, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, 'li'))
                )
                li.click()
                self.log_signal.emit(f"列表检索成功，《{li.text}》即将开始播放")
                # 使用 WebDriverWait 等待 li 中对应的按钮可点击之后点击它
                play_button = WebDriverWait(self.driver, 10).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, 'button.vjs-big-play-button'))
                )
                play_button.click()

                video_time = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, 'span.vjs-duration-display'))
                )
                print(video_time.text)
                self.log_signal.emit(
                    f"{time.strftime('%H:%M:%S',time.localtime(time.time()))}:正在播放《{li.text}》。"
                    f"{index + 1}/{len(ul_elements)}，时长{video_time.text}")
                video_complete = False
                start_time = time.time()
                while not video_complete and (time.time() - start_time) < 3600:
                    video_complete = check_video_status(self.driver)
                    time.sleep(5)
                if video_complete:
                    self.log_signal.emit(f"{li.text}播放完毕")
                else:
                    print(f"{li.text}超时未播放完毕")
                time.sleep(2)
                if index == len(ul_elements) - 1:
                    break
            except Exception as e:
                print(f"处理{li_texts[index]}时出错: {e}")


class MainWindow(QMainWindow, Ui_Form):
    def __init__(self):
        super().__init__()
        self.setupUi(self)
        self.setWindowIcon(QIcon('icon/花.png'))
        self.setFixedSize(340, 444)

        QApplication.setStyle(QStyleFactory.create('Fusion'))
        self.driver = None

        self.pushButton_login.clicked.connect(self.handle_login)
        self.pushButton_start.clicked.connect(self.handle_start_learning)

        self.login_thread = None
        self.learning_thread = None

    @pyqtSlot()
    def handle_login(self):
        username = self.lineEdit_id.text()
        password = self.lineEdit_pwd.text()

        self.login_thread = LoginThread(username, password)
        self.login_thread.login_finished.connect(self.handle_login_result)
        self.login_thread.driver_ready.connect(self.handle_driver_ready)
        self.login_thread.start()

    @pyqtSlot(str)
    def handle_login_result(self, result):
        self.textEdit_status.clear()
        self.textEdit_status.append(result)

    @pyqtSlot(object)
    def handle_driver_ready(self, driver):
        self.driver = driver
        self.textEdit_status.append("准备就绪，请点击开始学习按钮")

    @pyqtSlot()
    def handle_start_learning(self):
        if self.driver:
            self.learning_thread = LearningThread(self.driver)
            self.learning_thread.log_signal.connect(self.update_log)  # 连接信号到日志更新槽函数
            self.learning_thread.start()
        else:
            self.textEdit_status.clear()
            self.textEdit_status.append("请先登录，登录成功后再点击开始学习")

    @pyqtSlot(str)
    def update_log(self, log_text):
        self.textEdit_log.append(log_text)  # 更新日志内容

    def closeEvent(self, event):
        if self.driver:
            self.driver.quit()
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
