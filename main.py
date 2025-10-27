from kivymd.app import MDApp
from kivy.lang import Builder
from kivy.core.window import Window
from kivy.properties import StringProperty, BooleanProperty
from kivy.uix.screenmanager import ScreenManager, Screen, SwapTransition
from kivy.core.audio import SoundLoader
import sqlite3
from datetime import datetime
from kivy.clock import Clock
from kivy.uix.textinput import TextInput

from kivymd.uix.dialog import MDDialog
from kivymd.uix.button import MDFlatButton

# Window.size = (310, 600)

class KeyboardThemeStyle(Screen):
    pass

class HelpScreen(Screen):
    pass


class NoKeyboardTextInput(TextInput):
    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            # Handle the touch but don't show keyboard
            self.focus = True
            return True
        return super().on_touch_down(touch)

    def _on_focus(self, instance, value):
        if value:
            # Remove focus immediately to prevent keyboard
            self.focus = False


class LogScreen(Screen):
    display_limit = 10
    current_offset = 0
    has_more_records = BooleanProperty(False)
    delete_dialog = None

    def on_pre_enter(self):
        self.current_offset = 0
        self.load_history()

    def check_more_records(self):
        """Check if more records exist beyond current offset"""
        try:
            conn = sqlite3.connect('kirat_cal.db')
            cursor = conn.cursor()
            # Check if records exist beyond current display
            cursor.execute('SELECT COUNT(*) FROM calu_activity')
            total_records = cursor.fetchone()[0]
            conn.close()
            self.has_more_records = total_records > (self.current_offset + self.display_limit)
        except Exception as e:
            print(f"Error checking records: {e}")
            self.has_more_records = False

    def load_history(self, load_more=False):
        try:
            if load_more:
                self.current_offset += self.display_limit
            else:
                self.current_offset = 0

            conn = sqlite3.connect('kirat_cal.db')
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM calu_activity 
                ORDER BY id DESC 
                LIMIT ? OFFSET ?
            ''', (self.display_limit, self.current_offset))
            records = cursor.fetchall()
            conn.close()

            self.check_more_records()  # Update has_more_records

            if not records and not load_more:
                self.ids.log_label.text = "[size=20sp][b]No history found[/b][/size]"
                self.ids.log_label.markup = True
                return

            history_text = "[size=20sp][b]Calculation History:[/b]\n\n" if not load_more else ""

            if load_more and self.ids.log_label.text:
                history_text = self.ids.log_label.text + "\n\n"

            for record in records:
                id, expression, result, ts_eng, ts_nep, ts_lim = record
                main_screen = self.manager.get_screen('main')
                num_system = main_screen.current_num_system

                # Format timestamp
                timestamp = ts_lim if num_system == "limbu" else ts_nep if num_system == "nepali" else ts_eng

                # Convert numbers
                if num_system != "english":
                    expr_display = main_screen.convert_from_english(expression) if expression else ""
                    result_display = main_screen.convert_from_english(result) if result else ""
                else:
                    expr_display = expression if expression else ""
                    result_display = result if result else ""

                history_text += f"[size=18sp][b]{expr_display} = {result_display}[/b][/size]\n"
                history_text += f"[size=12sp]{timestamp}[/size]"
                history_text += f"      [color=ff0000][ref=del_{id}][size=12sp][Delete][/size][/ref][/color]\n\n"

            # Add Load More button if more records exist
            if self.has_more_records:
                history_text += "[size=18sp][color=0000ff][ref=load_more][Load More...][/ref][/color][/size]"
            else:
                history_text += "[size=18sp][color=808080]No more records[/color][/size]"

            self.ids.log_label.text = history_text
            self.ids.log_label.markup = True

        except Exception as e:
            print(f"Error loading history: {e}")
            self.ids.log_label.text = "Error loading history"

    def show_delete_confirmation(self, record_id):
        """Show confirmation dialog before deleting"""
        if self.delete_dialog:
            self.delete_dialog.dismiss()

        # Get the app instance to access theme_cls
        app = MDApp.get_running_app()

        self.delete_dialog = MDDialog(
            title="Confirm Delete",
            text="Are you sure you want to delete this record?",
            buttons=[
                MDFlatButton(
                    text="CANCEL",
                    theme_text_color="Custom",
                    text_color=app.theme_cls.primary_color,
                    on_release=lambda x: self.delete_dialog.dismiss()
                ),
                MDFlatButton(
                    text="DELETE",
                    theme_text_color="Custom",
                    text_color=(1, 0, 0, 1),  # Red color for delete
                    on_release=lambda x: self.confirm_delete(record_id)
                ),
            ],
        )
        self.delete_dialog.open()

    def confirm_delete(self, record_id):
        """Actually delete the record after confirmation"""
        try:
            if self.delete_dialog:
                self.delete_dialog.dismiss()

            conn = sqlite3.connect('kirat_cal.db')
            cursor = conn.cursor()
            cursor.execute('DELETE FROM calu_activity WHERE id = ?', (record_id,))
            conn.commit()
            conn.close()

            # Show success message
            self.show_delete_success()

            # Reload history
            self.load_history()

        except Exception as e:
            print(f"Error deleting record: {e}")
            # Show error message
            self.show_delete_error(str(e))

    def show_delete_success(self):
        """Show success message after deletion"""
        # Get the app instance to access theme_cls
        app = MDApp.get_running_app()

        success_dialog = MDDialog(
            title="Success",
            text="Record deleted successfully!",
            buttons=[
                MDFlatButton(
                    text="OK",
                    theme_text_color="Custom",
                    text_color=app.theme_cls.primary_color,
                    on_release=lambda x: success_dialog.dismiss()
                ),
            ],
        )
        success_dialog.open()

    def show_delete_error(self, error_msg):
        """Show error message if deletion fails"""
        # Get the app instance to access theme_cls
        app = MDApp.get_running_app()

        error_dialog = MDDialog(
            title="Error",
            text=f"Failed to delete record: {error_msg}",
            buttons=[
                MDFlatButton(
                    text="OK",
                    theme_text_color="Custom",
                    text_color=app.theme_cls.primary_color,
                    on_release=lambda x: error_dialog.dismiss()
                ),
            ],
        )
        error_dialog.open()

    def on_ref_press(self, ref):
        """Handle reference presses (delete and load more links)"""
        if ref.startswith('del_'):
            record_id = ref[4:]  # Extract record ID from 'del_123'
            self.show_delete_confirmation(record_id)
        elif ref == 'load_more' and self.has_more_records:
            self.load_history(load_more=True)


class MainScreen(Screen):
    current_input = StringProperty("")
    current_result = StringProperty("0")
    current_num_system = StringProperty("limbu")
    font_name = StringProperty("assets/font/CODE2000.TTF")
    focused_field = StringProperty("input")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.operators = ['+', '-', '×', '÷', '%']
        self.last_was_operator = False
        self.font_name = "assets/font/CODE2000.TTF"
        self.sound = None

        self.nepali_numbers = ['०', '१', '२', '३', '४', '५', '६', '७', '८', '९']
        self.limbu_numbers = ['᥆', '᥇', '᥈', '᥉', '᥊', '᥋', '᥌', '᥍', '᥎', '᥏']

        self.init_database()
        self.init_sound()
        Clock.schedule_once(self.update_hint_colors)  # Changed from _update_hint_colors to update_hint_colors

    def update_hint_colors(self, dt=None):  # Changed method name and made dt optional
        """Force update hint text colors with absolute values"""
        # These colors will work in both themes
        dark_gray = [0.3, 0.3, 0.3, 1]  # For light theme
        light_gray = [0.9, 0.9, 0.9, 1]  # For dark theme

        # Get current theme
        app = MDApp.get_running_app()
        hint_color = dark_gray if app.theme_cls.theme_style == "Light" else light_gray

        # Apply to both text fields
        self.ids.input_text.hint_text_color = hint_color
        self.ids.result_text.hint_text_color = hint_color

        # Force refresh the canvas
        self.ids.input_text.canvas.ask_update()
        self.ids.result_text.canvas.ask_update()

    def init_sound(self):
        try:
            self.sound = SoundLoader.load('assets/sound/click.mp3')
            if not self.sound:
                print("Sound file not found or couldn't be loaded")
        except Exception as e:
            print(f"Error loading sound: {e}")

    def init_database(self):
        try:
            conn = sqlite3.connect('kirat_cal.db')
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS calu_activity (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    expression TEXT,
                    result TEXT,
                    timestamp_english TEXT,
                    timestamp_nepali TEXT,
                    timestamp_limbu TEXT
                )
            ''')
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Database error: {e}")

    def play_sound(self):
        if self.sound:
            try:
                self.sound.play()
            except Exception as e:
                print(f"Error playing sound: {e}")

    def convert_to_english(self, text):
        if not text:
            return text
        if self.current_num_system == "english":
            return text
        elif self.current_num_system == "nepali":
            return ''.join([str(self.nepali_numbers.index(c)) if c in self.nepali_numbers else c for c in text])
        elif self.current_num_system == "limbu":
            return ''.join([str(self.limbu_numbers.index(c)) if c in self.limbu_numbers else c for c in text])
        return text

    def convert_from_english(self, text):
        if not text:
            return text
        if self.current_num_system == "english":
            return text
        elif self.current_num_system == "nepali":
            return ''.join([self.nepali_numbers[int(c)] if c.isdigit() else c for c in text])
        elif self.current_num_system == "limbu":
            return ''.join([self.limbu_numbers[int(c)] if c.isdigit() else c for c in text])
        return text

    def calculate_percentage(self):
        try:
            if not self.current_input:
                self.current_result = self.convert_from_english("0")
                return True

            english_input = self.convert_to_english(self.current_input)

            if english_input.endswith('%'):
                num_part = english_input[:-1]
                if not num_part:
                    self.current_result = self.convert_from_english("0")
                    self.current_input = ""
                    return True

                try:
                    value = float(num_part)
                    percentage = value / 100
                    # Format to 2 decimal places
                    result_str = "{:.2f}".format(float(percentage)).rstrip('0').rstrip(
                        '.') if percentage % 1 else "{:.0f}".format(percentage)
                    self.current_result = self.convert_from_english(result_str)
                    self.current_input = ""
                    return True
                except ValueError:
                    self.current_result = self.convert_from_english("0")
                    return True

            if '%' in english_input:
                parts = english_input.split('%')
                if len(parts) != 2 or parts[1] != '':
                    self.current_result = self.convert_from_english("0")
                    return True

                expr_part = parts[0]
                if not expr_part:
                    self.current_result = self.convert_from_english("0")
                    self.current_input = ""
                    return True

                operators = {'+', '-', '×', '÷', '*', '/'}
                last_op = None
                last_op_pos = -1
                for op in operators:
                    pos = expr_part.rfind(op)
                    if pos > last_op_pos:
                        last_op_pos = pos
                        last_op = op

                if last_op:
                    left_part = expr_part[:last_op_pos]
                    right_part = expr_part[last_op_pos + 1:]

                    try:
                        left_num = float(left_part) if left_part else 0.0
                        right_num = float(right_part) if right_part else 0.0

                        op = last_op.replace('×', '*').replace('÷', '/')

                        if op == '+':
                            result = left_num + (left_num * right_num / 100)
                        elif op == '-':
                            result = left_num - (left_num * right_num / 100)
                        elif op == '*':
                            result = left_num * (right_num / 100)
                        elif op == '/':
                            if right_num == 0:
                                self.current_result = self.convert_from_english("0")
                                return True
                            result = left_num / (right_num / 100)

                        # Format to 2 decimal places
                        result_str = "{:.2f}".format(float(result)).rstrip('0').rstrip(
                            '.') if result % 1 else "{:.0f}".format(result)
                        self.current_result = self.convert_from_english(result_str)
                        self.current_input = ""
                        return True
                    except (ValueError, ZeroDivisionError):
                        self.current_result = self.convert_from_english("0")
                        return True
                else:
                    try:
                        value = float(expr_part)
                        percentage = value / 100
                        # Format to 2 decimal places
                        result_str = "{:.2f}".format(float(percentage)).rstrip('0').rstrip(
                            '.') if percentage % 1 else "{:.0f}".format(percentage)
                        self.current_result = self.convert_from_english(result_str)
                        self.current_input = ""
                        return True
                    except ValueError:
                        self.current_result = self.convert_from_english("0")
                        return True

            return False
        except Exception as e:
            print(f"Percentage calculation error: {e}")
            self.current_result = self.convert_from_english("0")
            return True

    def nep_num_press(self, button_text):
        if button_text == "NEP_NUM" and self.current_num_system != "nepali":
            # Convert existing content before changing system
            self.convert_existing_content("nepali")
            self.current_num_system = "nepali"
            self.font_name = "assets/font/CODE2000.TTF"

    def lim_num_press(self, button_text):
        if button_text == "LIM_NUM" and self.current_num_system != "limbu":
            # Convert existing content before changing system
            self.convert_existing_content("limbu")
            self.current_num_system = "limbu"
            self.font_name = "assets/font/CODE2000.TTF"

    def eng_num_press(self, button_text):
        if button_text == "ENG_NUM" and self.current_num_system != "english":
            # Convert existing content before changing system
            self.convert_existing_content("english")
            self.current_num_system = "english"
            self.font_name = "Roboto"

    def convert_existing_content(self, new_system):
        """Convert current input and result to new number system"""
        # Convert current input
        if self.current_input:
            # Convert to English first, then to new system
            english_input = self.convert_to_english(self.current_input)
            self.current_input = self.convert_from_english_system(english_input, new_system)

        # Convert current result
        if self.current_result and self.current_result != "0" and self.current_result != "Error":
            english_result = self.convert_to_english(self.current_result)
            self.current_result = self.convert_from_english_system(english_result, new_system)

    def convert_from_english_system(self, text, to_system):
        """Convert text from English numbers to specified system"""
        if not text or to_system == "english":
            return text

        number_map = {
            "nepali": self.nepali_numbers,
            "limbu": self.limbu_numbers
        }

        numbers = number_map[to_system]
        result = []
        for char in text:
            if char.isdigit():
                result.append(numbers[int(char)])
            else:
                result.append(char)
        return ''.join(result)

    def on_button_press(self, button_text):
        self.set_focus("input")

        if button_text == "AC":
            self.current_input = ""
            self.current_result = "0"
            self.last_was_operator = False
            return

        if button_text == "DEL":
            if self.current_input:
                self.current_input = self.current_input[1:]
            return

        if button_text == "⌫":
            if self.current_input:
                self.current_input = self.current_input[:-1]
            return

        if button_text == "=":
            self.calculate_result()
            return

        if button_text == "%":
            self.current_input += button_text
            self.calculate_percentage()
            return

        # If we have a result and user presses an operator, start new calculation with result
        if button_text in self.operators and not self.current_input and self.current_result != "0":
            # Convert result back to english for calculation
            english_result = self.convert_to_english(self.current_result)
            self.current_input = english_result + button_text
            self.last_was_operator = True
            return

        if button_text in self.operators:
            if self.current_input and self.last_was_operator:
                self.current_input = self.current_input[:-1] + button_text
                return
            elif not self.current_input:
                return
            self.last_was_operator = True
        else:
            self.last_was_operator = False

        self.current_input += button_text

    def convert_timestamp(self, timestamp_str, number_system):
        if number_system == "english":
            return timestamp_str

        number_map = {
            "nepali": ['०', '१', '२', '३', '४', '५', '६', '७', '८', '९'],
            "limbu": ['᥆', '᥇', '᥈', '᥉', '᥊', '᥋', '᥌', '᥍', '᥎', '᥏']
        }

        digits = number_map[number_system]
        converted = []
        for char in timestamp_str:
            if char.isdigit():
                converted.append(digits[int(char)])
            else:
                converted.append(char)
        return ''.join(converted)

    def save_calculation(self, expression, result):
        try:
            timestamp = datetime.now().strftime('%Y-%m-%d | %H:%M:%S')

            timestamp_english = timestamp
            timestamp_nepali = self.convert_timestamp(timestamp, "nepali")
            timestamp_limbu = self.convert_timestamp(timestamp, "limbu")

            conn = sqlite3.connect('kirat_cal.db')
            cursor = conn.cursor()

            cursor.execute('''
                INSERT INTO calu_activity 
                (expression, result, timestamp_english, timestamp_nepali, timestamp_limbu)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                expression,
                result,
                timestamp_english,
                timestamp_nepali,
                timestamp_limbu
            ))

            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Error saving calculation: {e}")

    def calculate_result(self):
        try:
            if not self.current_input:
                self.current_result = self.convert_from_english("0")
                return

            # Store the original input for display
            original_input = self.current_input
            english_input = self.convert_to_english(self.current_input)

            if '%' in english_input:
                if english_input.endswith('%'):
                    value_part = english_input[:-1]
                    try:
                        value = float(value_part) if value_part else 0
                        result = value / 100
                        # Format to 2 decimal places
                        result_str = "{:.2f}".format(float(result)).rstrip('0').rstrip(
                            '.') if result % 1 else "{:.0f}".format(result)
                        # Display expression and result
                        self.current_result = self.convert_from_english(result_str)
                        self.save_calculation(original_input, self.convert_from_english(result_str))
                        self.current_input = ""
                        return
                    except ValueError:
                        pass

                parts = english_input.split('%')
                if len(parts) == 2 and parts[1] == '':
                    expr_part = parts[0]
                    operators = {'+', '-', '×', '÷', '*', '/'}
                    last_op = None
                    last_op_pos = -1
                    for op in operators:
                        pos = expr_part.rfind(op)
                        if pos > last_op_pos:
                            last_op_pos = pos
                            last_op = op

                    if last_op:
                        left_part = expr_part[:last_op_pos]
                        right_part = expr_part[last_op_pos + 1:]
                        try:
                            left_num = float(left_part) if left_part else 0
                            right_num = float(right_part) if right_part else 0

                            if last_op in ('+', '-'):
                                percentage = right_num / 100
                                if last_op == '+':
                                    result = left_num + (left_num * percentage)
                                else:
                                    result = left_num - (left_num * percentage)
                            else:
                                percentage = right_num / 100
                                if last_op in ('×', '*'):
                                    result = left_num * percentage
                                else:
                                    if percentage == 0:
                                        self.current_result = self.convert_from_english("Error")
                                        return
                                    result = left_num / percentage

                            # Format to 2 decimal places
                            result_str = "{:.2f}".format(float(result)).rstrip('0').rstrip(
                                '.') if result % 1 else "{:.0f}".format(result)
                            # Display result
                            self.current_result = self.convert_from_english(result_str)
                            self.save_calculation(original_input, self.convert_from_english(result_str))
                            self.current_input = ""
                            return
                        except (ValueError, ZeroDivisionError):
                            pass

            # Remove trailing operators
            while english_input and english_input[-1] in ['+', '-', '×', '÷', '*', '/']:
                english_input = english_input[:-1]

            if not english_input:
                self.current_result = self.convert_from_english("0")
                self.current_input = ""
                return

            expression = english_input.replace('×', '*').replace('÷', '/')

            try:
                result = eval(expression)
                # Format to 2 decimal places
                result_str = "{:.2f}".format(float(result)).rstrip('0').rstrip('.') if result % 1 else "{:.0f}".format(
                    result)

                # Save the calculation
                self.save_calculation(original_input, self.convert_from_english(result_str))

                # Set the result and keep it for further calculations
                self.current_result = self.convert_from_english(result_str)

                # Clear input but keep result for next operation
                self.current_input = ""

            except (SyntaxError, ZeroDivisionError, TypeError, NameError):
                self.current_result = self.convert_from_english("Error")
                self.current_input = ""

        except Exception as e:
            print(f"Calculation error: {e}")
            self.current_result = self.convert_from_english("Error")
            self.current_input = ""



    def set_focus(self, field_name):
        self.focused_field = field_name
        if field_name == "input":
            self.ids.input_text.focus = True
            self.ids.result_text.focus = False
        else:
            self.ids.input_text.focus = False
            self.ids.result_text.focus = True

class CalculatorApp(MDApp):
    def build(self):
        self.theme_cls.primary_palette = "Teal"
        self.theme_cls.theme_style = "Light"

        sm = ScreenManager(transition=SwapTransition())
        sm.add_widget(MainScreen(name='main'))
        sm.add_widget(HelpScreen(name='help_screen'))
        sm.add_widget(LogScreen(name='log_screen'))
        sm.add_widget(KeyboardThemeStyle(name='keyboard_theme_style'))

        Builder.load_file("calculator.kv")
        return sm

    def on_start(self):
        # Call update_hint_colors directly on the main screen
        main_screen = self.root.get_screen('main')
        # main_screen = self.root.get_screen('startup_screen')
        main_screen.update_hint_colors()

    def theme_changer(self):
        self.theme_cls.theme_style = 'Dark' if self.theme_cls.theme_style == 'Light' else 'Light'
        # Call the renamed method
        main_screen = self.root.get_screen('main')
        main_screen.update_hint_colors()  # Changed from _update_hint_colors to update_hint_colors

    def update_theme_colors(self):
        main_screen = self.root.get_screen('main')
        if hasattr(main_screen, 'update_hint_colors'):
            main_screen.update_hint_colors()

    def open_keyboard_theme(self):
        self.root.current = "keyboard_theme_style"

    def play_sound(self):
        sound = SoundLoader.load('assets/sound/click.mp3')
        if sound:
            sound.play()

    def open_help(self):
        self.root.current = "help_screen"

    def return_to_HomeScreen(self):
        self.root.current = "main"
        self.play_sound()

    def open_log(self):
        self.root.current = "log_screen"

if __name__ == "__main__":
    CalculatorApp().run()