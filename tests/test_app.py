from monitor.app import MonitorApp
from monitor.core import Group, Post


def test_gui_config_history_open_link_and_busy_controls(tmp_path, monkeypatch):
    app = MonitorApp(tmp_path)
    app.withdraw()
    try:
        app.settings.groups = [Group("IT Jobs", "https://www.facebook.com/groups/123")]
        app.draw_groups()
        app.interval.set("30")
        app.keywords.delete("1.0", "end")
        app.keywords.insert("1.0", "java intern\nspring boot")
        app.save_settings()
        saved = app.store.load_settings()
        assert saved.interval_minutes == 30
        assert saved.keywords == ["java intern", "spring boot"]
        app.set_busy(True)
        assert app.start_button.cget("state") == "disabled"
        assert app.stop_button.cget("state") == "normal"
        before = app.keywords.get("1.0", "end")
        app.keywords.insert("end", "should not be editable while running")
        assert app.keywords.get("1.0", "end") == before
        app.set_busy(False)
        assert app.start_button.cget("state") == "normal"
        post = Post(
            "https://www.facebook.com/groups/123/posts/456",
            "IT Jobs",
            "https://www.facebook.com/groups/123",
            "Tuyển Java Intern",
            ["java intern"],
        )
        app.store.save_post(post)
        app.refresh_results()
        key = app.table.get_children()[0]
        app.table.selection_set(key)
        app.show_details()
        assert post.content in app.details.get("1.0", "end")
        opened = []
        monkeypatch.setattr("monitor.app.webbrowser.open", opened.append)
        app.open_post()
        assert opened == [post.url]
        app.remove_group(saved.groups[0].url)
        assert app.settings.groups == []
        assert app.store.count() == 1
    finally:
        app.destroy()
