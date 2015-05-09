import re

from browsergui import GUI, Text, Button

from . import BrowserGUITestCase


class GUITest(BrowserGUITestCase):

  def test_construction(self):
    gui = GUI()

    GUI(Text("left"), Text("hi"))

    with self.assertRaises(TypeError):
      gui = GUI(0)

  def test_event_dispatch(self):
    decoy1 = Button()
    button = Button()
    decoy2 = Button()
    button.set_callback(self.set_last_event)

    gui = GUI(decoy1, button, decoy2)

    event = {'type': CLICK, 'id': button.id}
    with self.assertSetsEvent(event):
      gui.handle_event(event)

  def test_html(self):
    button = Button()
    text = Text("hi lol")
    gui = GUI(button, text)
    html = gui.html()

    self.assertHTMLIn(button.html, html)
    self.assertHTMLIn(text.html, html)

  def test_command_stream(self):
    gui = GUI()
    stream = gui.command_stream()

    while not stream.empty():
      stream.get()

    gui.send_command("foo")
    self.assertEqual("foo", stream.get())
    self.assertTrue(stream.empty())

    stream2 = gui.command_stream()
    while not stream2.empty():
      stream2.get()

    gui.send_command("bar")
    self.assertEqual("bar", stream.get())
    self.assertTrue(stream.empty())
    self.assertEqual("bar", stream2.get())
    self.assertTrue(stream2.empty())

  def test_callbacks_produce_commands(self):
    button_with_predefined_callback = Button(callback=(lambda event: None))
    button_with_later_callback = Button()
    gui = GUI(button_with_predefined_callback, button_with_later_callback)
    stream = gui.command_stream()

    self.assertIn(button_with_predefined_callback.id, stream.get())
    self.assertTrue(stream.empty())

    button.set_callback(lambda event: None)
    self.assertIn(button_with_later_callback.id, stream.get())
    self.assertTrue(stream.empty())
