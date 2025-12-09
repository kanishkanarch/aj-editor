import termios
import curses
import sys
import os
import copy

LINE_NUMBER_WIDTH = 5
RECENT_FILES = '.editor_recent'

# Keywords to highlight (for Python files)
HIGHLIGHT_KEYWORDS = {
    'def': curses.A_BOLD,
    'class': curses.A_BOLD,
    'import': curses.A_BOLD,
    'from': curses.A_BOLD,
    'return': curses.A_BOLD,
}

def draw_title(stdscr, filename, filetype):
    title = "[ Editing: {} ] - Editor".format(filename if filename else "New Buffer")
    try:
        stdscr.addstr(0, 0, title.center(curses.COLS - 1), curses.A_REVERSE)
    except curses.error:
        pass

_prev_menu_rows = 0  # tracks how many menu rows were drawn last time

def draw_menu(stdscr, height):
    global _prev_menu_rows
    menu = "^G Help  ^O Write Out  ^W Where Is  ^\\ Replace  ^_ GoTo  ^K Cut  ^U Paste  ^Z Undo  ^Y Redo  ^X Exit"

    width = curses.COLS - 1
    divider_row = height - 2
    last_row = height - 1
    for r in range(last_row - _prev_menu_rows + 1, last_row + 1):
        if r >= 1:
            try:
                stdscr.move(r, 0)
                stdscr.clrtoeol()
            except curses.error:
                pass
    try:
        stdscr.addstr(divider_row, 0, "-" * width)
    except curses.error:
        pass
    chunks = [menu[i:i + width] for i in range(0, len(menu), width)]
    row = last_row
    for chunk in reversed(chunks):
        if row < 1:
            break
        try:
            stdscr.addstr(row, 0, chunk)
        except curses.error:
            pass
        row -= 1
    _prev_menu_rows = len(chunks)

def draw_status(stdscr, message, height):
    stdscr.addstr(height-3, 0, message.ljust(curses.COLS-1))

def prompt(stdscr, height, prompt_text):
    curses.echo()
    stdscr.addstr(height-4, 0, prompt_text)
    user_input = stdscr.getstr(height-4, len(prompt_text), 60).decode()
    curses.noecho()
    return user_input

def word_wrap(line, width):
    return [line[i:i+width] for i in range(0, len(line), width)] if len(line) > width else [line]

def save_recent_file(filename):
    try:
        with open(RECENT_FILES, 'a') as f:
            f.write(filename + '\n')
    except Exception:
        pass

def load_recent_files():
    if os.path.exists(RECENT_FILES):
        with open(RECENT_FILES, 'r') as f:
            return [line.strip() for line in f if line.strip()]
    return []

def detect_filetype(filename):
    if filename and filename.endswith('.py'):
        return 'python'
    return 'text'

def disable_ctrl_z():
    try:
        fd = sys.stdin.fileno()
        attrs = termios.tcgetattr(fd)
        attrs[6][termios.VSUSP] = 0
        termios.tcsetattr(fd, termios.TCSANOW, attrs)
    except Exception:
        pass

def restore_ctrl_z():
    try:
        fd = sys.stdin.fileno()
        attrs = termios.tcgetattr(fd)
        attrs[6][termios.VSUSP] = b'\x1A'
        termios.tcsetattr(fd, termios.TCSANOW, attrs)
    except Exception:
        pass

def editor(stdscr, filename=None):
    curses.curs_set(1)
    curses.mousemask(1)
    stdscr.keypad(True)

    lines = ['']
    cursor_y, cursor_x = 0, 0
    screen_y_offset = 0
    status_msg = "Welcome to Editor! Ctrl-G for Help."
    modified = False
    clipboard_line = ""
    undo_stack = []
    redo_stack = []
    filetype = detect_filetype(filename)

    def save_undo():
        undo_stack.append(copy.deepcopy(lines))
        if len(undo_stack) > 100:
            undo_stack.pop(0)
        redo_stack.clear()

    if filename:
        try:
            with open(filename, 'r') as f:
                lines = f.read().splitlines()
            if not lines:
                lines = ['']
            save_recent_file(filename)
        except FileNotFoundError:
            status_msg = f"New file: {filename}"

    while True:
        stdscr.clear()
        height, width = stdscr.getmaxyx()

        # Compute dynamic menu height
        menu_text = "^G Help  ^O Write Out  ^W Where Is  ^\\ Replace  ^_ GoTo  ^K Cut  ^U Paste  ^Z Undo  ^Y Redo  ^X Exit"
        menu_chunks = [menu_text[i:i+width-1] for i in range(0, len(menu_text), width-1)]
        menu_height = len(menu_chunks)

        text_height = height - 4 - menu_height  # shrink text area to leave room for menu
        text_width = width - LINE_NUMBER_WIDTH

        if cursor_y < screen_y_offset:
            screen_y_offset = cursor_y
        elif cursor_y >= screen_y_offset + text_height:
            screen_y_offset = cursor_y - text_height + 1

        # Title
        draw_title(stdscr, filename, filetype)

        wrapped_lines = []
        for original_idx, line in enumerate(lines):
            wrapped = word_wrap(line, text_width)
            for wline in wrapped:
                wrapped_lines.append((original_idx, wline))

        # Text Area
        for idx in range(text_height):
            wrapped_idx = screen_y_offset + idx
            if wrapped_idx < len(wrapped_lines):
                original_idx, wline = wrapped_lines[wrapped_idx]
                line_number = f"{original_idx+1}".rjust(LINE_NUMBER_WIDTH-1) + " "
                try:
                    stdscr.addstr(idx+1, 0, line_number)
                    words = wline.split(' ')
                    pos = LINE_NUMBER_WIDTH
                    for word in words:
                        attr = curses.A_NORMAL
                        if filetype == 'python' and word in HIGHLIGHT_KEYWORDS:
                            attr = HIGHLIGHT_KEYWORDS[word]
                        stdscr.addstr(idx+1, pos, word + ' ', attr)
                        pos += len(word) + 1
                except curses.error:
                    pass

        draw_status(stdscr, status_msg, height)
        draw_menu(stdscr, height)

        visible_line_idx = 0
        for i, (orig_idx, _) in enumerate(wrapped_lines):
            if orig_idx == cursor_y:
                if cursor_x <= len(wrapped_lines[i][1]):
                    visible_line_idx = i
                    break
                cursor_x -= len(wrapped_lines[i][1])

        screen_cursor_y = visible_line_idx - screen_y_offset
        try:
            stdscr.move(screen_cursor_y+1, cursor_x + LINE_NUMBER_WIDTH)
        except curses.error:
            pass

        stdscr.refresh()

        key = stdscr.getch()

        if key == curses.KEY_MOUSE:
            try:
                _, mx, my, _, _ = curses.getmouse()
                if 1 <= my < text_height+1:
                    cursor_y = screen_y_offset + (my - 1)
                    cursor_y = max(0, min(cursor_y, len(lines)-1))
                    cursor_x = max(0, min(mx - LINE_NUMBER_WIDTH, len(lines[cursor_y])))
            except:
                pass

        elif key == curses.KEY_UP:
            cursor_y = max(0, cursor_y-1)
            cursor_x = min(cursor_x, len(lines[cursor_y]))
        elif key == curses.KEY_DOWN:
            cursor_y = min(len(lines)-1, cursor_y+1)
            cursor_x = min(cursor_x, len(lines[cursor_y]))
        elif key == curses.KEY_LEFT:
            if cursor_x > 0:
                cursor_x -= 1
            elif cursor_y > 0:
                cursor_y -= 1
                cursor_x = len(lines[cursor_y])
        elif key == curses.KEY_RIGHT:
            if cursor_x < len(lines[cursor_y]):
                cursor_x += 1
            elif cursor_y < len(lines)-1:
                cursor_y += 1
                cursor_x = 0
        elif key in (curses.KEY_BACKSPACE, 127, 8):
            save_undo()
            modified = True
            if cursor_x > 0:
                lines[cursor_y] = lines[cursor_y][:cursor_x-1] + lines[cursor_y][cursor_x:]
                cursor_x -= 1
            elif cursor_y > 0:
                prev_len = len(lines[cursor_y-1])
                lines[cursor_y-1] += lines[cursor_y]
                lines.pop(cursor_y)
                cursor_y -= 1
                cursor_x = prev_len
        elif key == 10:
            save_undo()
            modified = True
            new_line = lines[cursor_y][cursor_x:]
            lines[cursor_y] = lines[cursor_y][:cursor_x]
            lines.insert(cursor_y+1, new_line)
            cursor_y += 1
            cursor_x = 0
        elif key == 9:
            save_undo()
            modified = True
            tab_spaces = "    "
            lines[cursor_y] = lines[cursor_y][:cursor_x] + tab_spaces + lines[cursor_y][cursor_x:]
            cursor_x += len(tab_spaces)
        elif key == 24:  # Ctrl-X Exit
            if modified:
                status_msg = "Unsaved changes! Ctrl-O to save, Ctrl-X again to force exit."
                stdscr.clear()
                draw_status(stdscr, status_msg, height)
                draw_menu(stdscr, height)
                stdscr.refresh()
                confirm_exit = stdscr.getch()
                if confirm_exit == 24:
                    break
            else:
                break
        elif key == 15:  # Ctrl-O Save
            if not filename:
                filename = prompt(stdscr, height, "Save as: ")
                filetype = detect_filetype(filename)
            if filename:
                try:
                    if os.path.exists(filename):
                        backup_name = filename + "~"
                        os.rename(filename, backup_name)
                    with open(filename, 'w') as f:
                        f.write('\n'.join(lines))
                    save_recent_file(filename)
                    status_msg = f"Wrote {filename} (Backup created)"
                    modified = False
                except Exception as e:
                    status_msg = f"Error saving: {e}"
            else:
                status_msg = "Save cancelled."
        elif key == 7:  # Ctrl-G Help
            status_msg = "Editor Help: Ctrl-O Save | Ctrl-X Exit | Ctrl-\\ Replace | Ctrl-_ GoTo | Ctrl-K Cut | Ctrl-U Paste | Ctrl-Z Undo | Ctrl-Y Redo"
        elif key == 23:  # Ctrl-W Where Is
            search_term = prompt(stdscr, height, "Search: ")
            found = False
            for idx in range(cursor_y, len(lines)):
                if search_term in lines[idx]:
                    cursor_y = idx
                    cursor_x = lines[idx].find(search_term)
                    found = True
                    status_msg = f"Found '{search_term}'"
                    break
            if not found:
                status_msg = f"'{search_term}' not found!"
        elif key == 28:  # Ctrl-\
            save_undo()
            search_term = prompt(stdscr, height, "Replace - Find: ")
            replace_term = prompt(stdscr, height, "Replace - With: ")
            count = 0
            for i in range(len(lines)):
                if search_term in lines[i]:
                    lines[i] = lines[i].replace(search_term, replace_term)
                    count += 1
            modified = True
            status_msg = f"Replaced {count} occurrence(s)"
        elif key == 31:  # Ctrl-_
            try:
                goto_line = int(prompt(stdscr, height, "Goto Line: ")) - 1
                if 0 <= goto_line < len(lines):
                    cursor_y = goto_line
                    cursor_x = min(cursor_x, len(lines[cursor_y]))
                    status_msg = f"Jumped to line {goto_line+1}"
                else:
                    status_msg = "Invalid line number."
            except ValueError:
                status_msg = "Invalid input."
        elif key == 11:  # Ctrl-K Cut
            save_undo()
            clipboard_line = lines[cursor_y]
            lines.pop(cursor_y)
            if cursor_y >= len(lines):
                cursor_y = max(0, len(lines)-1)
            cursor_x = 0
            modified = True
            status_msg = "Line cut."
        elif key == 21:  # Ctrl-U Paste
            save_undo()
            lines.insert(cursor_y, clipboard_line)
            modified = True
            status_msg = "Line pasted."
        elif key == 26:  # Ctrl-Z Undo
            if undo_stack:
                redo_stack.append(copy.deepcopy(lines))
                lines = undo_stack.pop()
                status_msg = "Undo!"
        elif key == 25:  # Ctrl-Y Redo
            if redo_stack:
                undo_stack.append(copy.deepcopy(lines))
                lines = redo_stack.pop()
                status_msg = "Redo!"
        elif 32 <= key <= 126:
            save_undo()
            modified = True
            lines[cursor_y] = lines[cursor_y][:cursor_x] + chr(key) + lines[cursor_y][cursor_x:]
            cursor_x += 1

def main():
    script_name = os.path.basename(sys.argv[0])
    if len(sys.argv) == 2 and sys.argv[1] == '--recent':
        recent = load_recent_files()
        if not recent:
            print("No recent files found.")
            return
        print("Recent files:")
        for idx, file in enumerate(recent):
            print(f"{idx+1}: {file}")
        choice = input("Open which file (number)? ")
        try:
            index = int(choice) - 1
            filename = recent[index]
        except (ValueError, IndexError):
            print("Invalid selection.")
            return
    elif len(sys.argv) >= 2:
        filename = sys.argv[1]
    else:
        filename = None
        print(f"Starting a new buffer (no filename). You can save it later with Ctrl-O.")

    disable_ctrl_z()
    try:
        curses.wrapper(editor, filename)
    finally:
        restore_ctrl_z()

if __name__ == "__main__":
    main()

