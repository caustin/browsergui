import collections
import json
import weakref
import xml.dom.minidom
import xml.parsers.expat

CLICK = "click"
KEYDOWN = "keydown"
KEYUP = "keyup"

_unique_id_counter = 0
def unique_id():
  """Returns a new string suitable for an :class:`Element` id every time it's called."""
  global _unique_id_counter
  _unique_id_counter += 1
  return "_element_{}".format(_unique_id_counter)

class ParseError(Exception):
  """Raised when given HTML for an Element can't be parsed."""
  pass
class OrphanedError(Exception):
  """Raised when trying to do something nonsensical to an Element with no parent."""
  pass
class NotOrphanedError(Exception):
  """Raised when trying to give an Element a new parent without removing the old one."""
  pass
class NoSuchCallbackError(Exception):
  """Raised when trying to remove a nonexistent callback from an Element."""
  pass

def parse_tag(html):
  """Parses HTML into an XML element tree.

  :param html: the string to parse
  :type html: str
  :rtype: xml.dom.minidom.Element
  """
  try:
    return xml.dom.minidom.parseString(html).documentElement
  except xml.parsers.expat.ExpatError:
    raise ParseError("invalid html", html)

class Element(object):
  """A conceptual GUI element, like a button or a table.

  Elements are arranged in trees: an Element may have children (other Elements) or not, and it may have a parent or not.
  Every element has a unique identifier, accessible by the :func:`id` method.
  """
  def __init__(self, html=None, tag_name=None, children=()):
    if not ((html is None) ^ (tag_name is None)):
      raise TypeError("Element.__init__ must be given html or tag_name (but not both)")

    if html is None:
      html = "<{t}></{t}>".format(t=tag_name)

    self.tag = parse_tag(html)
    self.tag.attributes['id'] = unique_id()

    self.parent_weakref = None
    self.children = []
    self.callbacks = collections.defaultdict(list)

    for child in children:
      self.append(child)

  def __str__(self):
    return "(#{})".format(self.id)

  def __repr__(self):
    return "Element(id={!r})".format(self.id)

  def __hash__(self):
    return id(self)

  def __eq__(self, other):
    if isinstance(other, Element):
      return self.tag.toxml() == other.tag.toxml() and self.callbacks == other.callbacks

  @property
  def id(self):
    return self.tag.attributes['id'].value

  def walk(self):
    """Iterates over the Element and all the Elements below it in the tree."""
    yield self
    for child in self.children:
      for descendant in child.walk():
        yield descendant

  def append(self, child):
    """Add a new child after all existing children.

    :raises NotOrphanedError: if `child` already has a parent Element
    :raises TypeError: if `child` is not an Element
    """
    if not isinstance(child, Element):
      raise TypeError(child)
    if not child.orphaned:
      raise NotOrphanedError('only orphaned elements can be inserted')
    self.tag.appendChild(child.tag)
    self.children.append(child)
    self.register_child(child)

  def insert_before(self, sibling):
    """Inserts an Element immediately before this one in its parent.

    :raises OrphanedError: if this Element has no parent
    :raises NotOrphanedError: if `sibling` already has a parent Element
    :raises TypeError: if `sibling` is not an Element
    """
    if not isinstance(sibling, Element):
      raise TypeError(sibling)
    if not sibling.orphaned:
      raise NotOrphanedError('only orphaned elements can be inserted')
    if self.orphaned:
      raise OrphanedError("can't insert sibling for root node")
    self.parent.tag.insertBefore(sibling.tag, self.tag)
    self.parent.children.insert(self.parent.children.index(self), sibling)
    self.parent.register_child(sibling)

  def insert_after(self, sibling):
    """Like :func:`insert_before`, but inserts the new sibling after this one."""
    if not isinstance(sibling, Element):
      raise TypeError(sibling)
    if not sibling.orphaned:
      raise NotOrphanedError('only orphaned elements can be inserted')

    self.parent.tag.insertBefore(sibling.tag, None if self.next_sibling is None else self.next_sibling.tag)
    self.parent.children.insert(self.parent.children.index(self)+1, sibling)
    self.parent.register_child(sibling)

  @property
  def parent(self):
    """
    :returns: the element's parent, or None if the Element is orphaned
    """
    return (None if self.parent_weakref is None else self.parent_weakref())
  @parent.setter
  def parent(self, parent):
    if parent is None:
      self.parent_weakref = None
    elif self.orphaned:
      self.parent_weakref = weakref.ref(parent)
    else:
      raise NotOrphanedError('only orphaned elements can be given new parents')

  @property
  def next_sibling(self):
    """    
    :returns: the next child of the element's parent, or None if there isn't one.
    """
    if self.orphaned:
      return None
    siblings = self.parent.children
    i = siblings.index(self) + 1
    if i < len(siblings):
      return siblings[i]
    return None

  @property
  def previous_sibling(self):
    """Like :func:`next_sibling`, but returns parent's previous child."""
    if self.orphaned:
      return None
    siblings = self.parent.children
    i = siblings.index(self) - 1
    if i >= 0:
      return siblings[i]
    return None

  @property
  def html(self):
    """An HTML representation of the element and all its children."""
    return self.tag.toprettyxml()

  @property
  def orphaned(self):
    """Whether the Element has no parent.

    :rtype: bool
    """
    return (self.parent is None)

  @property
  def gui(self):
    """The GUI the element belongs to, or None if there is none."""
    return (None if self.orphaned else self.parent.gui)

  def extract(self):
    """Removes the element from its parent.

    :raises OrphanedError: if the element is already orphaned
    """
    if self.orphaned:
      raise OrphanedError("element already has no parent")
    self.parent.disown(self)

  def disown(self, child):
    """Removes a child from this element's list of children.

    Also, does bookkeeping for removing an element from the tree.

    :type child: Element
    :raises ValueError: if the given child is not a child of this element
    """
    self.children.remove(child)
    if self.gui is not None:
      self.gui.unregister_element(child)
    child.parent = None

  def register_child(self, child):
    """Does all the bookkeeping for when a new child has entered the tree.

    :type child: Element
    """
    child.parent = self
    if self.gui is not None:
      self.gui.register_element(child)

  def add_callback(self, event_type, callback):
    """Arranges for ``callback`` to be called whenever the Element handles an event of ``event_type``.

    :type event_type: str
    :type callback: a function of one argument (the event being handled)
    """
    self.callbacks[event_type].append(callback)
    if self.gui is not None:
      self.gui.note_callback_added(self, event_type, callback)

  def remove_callback(self, event_type, callback):
    """Stops calling ``callback`` when events of ``event_type`` are handled.

    For parameter information, see :func:`add_callback`.
    """
    if callback not in self.callbacks[event_type]:
      raise NoSuchCallbackError(event_type, callback)
    self.callbacks[event_type].remove(callback)
    if self.gui is not None:
      self.gui.note_callback_added(self, event_type, callback)

  def handle_event(self, event):
    """Calls all the callbacks registered for the given event's type.

    :type event: dict
    """
    for callback in self.callbacks[event['type']]:
      callback(event)

  def toggle_visibility(self):
    """Toggles whether the element can be seen or not."""
    self.gui.send_command("$({selector}).toggle()".format(selector=json.dumps("#"+self.id)))
    # TO DO: that only does JavaScript stuff - figure out how to make this more complete.
    # Probably requires a styling system.


class Text(Element):
  """Some simple text."""
  def __init__(self, text, tag_name="span"):
    if not isinstance(text, str):
      raise TypeError(text)
    super(Text, self).__init__(html="<{tag}></{tag}>".format(tag=tag_name))
    self._text = xml.dom.minidom.Text()
    self._text.data = text
    self.tag.appendChild(self._text)

  @property
  def text(self):
    """docstring"""
    return self._text.data
  @text.setter
  def text(self, value):
    """docstring"""
    if self.text == value:
      return

    self._text.data = value
    if self.gui is not None:
      self.gui.send_command("$({selector}).text({text})".format(selector=json.dumps("#"+self.id), text=json.dumps(self.text)))

class CodeSnippet(Text):
  """Inline text representing computer code."""
  def __init__(self, text):
    super(CodeSnippet, self).__init__(text, tag_name="code")
    self.tag.attributes['style'] = 'white-space: pre;'
class Paragraph(Text):
  """A block of plain text."""
  def __init__(self, text):
    super(Paragraph, self).__init__(text, tag_name="p")
class CodeBlock(Text):
  """A block of computer code."""
  def __init__(self, text):
    super(CodeBlock, self).__init__(text, tag_name="pre")

class Button(Text):
  """A simple button that does something when clicked."""
  def __init__(self, text="Click!", callback=None):
    """
    :param text: the label of the button
    :type text: str
    :param callback: the function to be called
    :type callback: function of zero arguments
    """
    if not isinstance(text, str):
      raise TypeError(text)
    super(Button, self).__init__(text, tag_name="button")
    if callback is not None:
      self.set_callback(callback)

  def set_callback(self, callback):
    """Sets the function to be called whenever the button is clicked.

    :param callback: the function to be called
    :type callback: function of zero arguments
    """
    if self.callbacks[CLICK]:
      self.remove_callback(CLICK, self.callbacks[CLICK][0])
    self.add_callback(CLICK, (lambda event: callback()))

class Container(Element):
  """Contains and groups other elements."""
  def __init__(self, *children, **kwargs):
    """
    :param children: the elements the Container should contain
    :type elements: :class:`Element`s
    :param kwargs: may contain the key "inline" specifying whether the container should be inline or not (default not)
    """
    self._inline = kwargs.pop("inline", False)
    super(Container, self).__init__(tag_name=("span" if self._inline else "div"), children=children, **kwargs)

class Image(Element):
  """An image. Don't use this, it's half-finished and I don't know why I committed it."""
  def __init__(self, location):
    super(Image, self).__init__(tag_name="img")
    raise NotImplementedError()
    self._location = _location
    if callback is not None:
      self.add_callback(CLICK, callback)
