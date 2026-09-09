// Preserve keyed elements across provider/clock updates. Replacing innerHTML
// every second resets hover timers and keyboard focus, breaking native tooltips.
export function patchChildren(parent, desired) {
  let cursor = parent.firstChild;
  for (const next of Array.from(desired.childNodes)) {
    const key = next.nodeType === 1 ? next.getAttribute("data-key") : null;
    let current = key === null ? cursor : Array.from(parent.children)
      .find(child => child.getAttribute("data-key") === key);
    if (!current || current.nodeType !== next.nodeType || current.nodeName !== next.nodeName
      || (key === null && current.nodeType === 1 && current.hasAttribute("data-key"))) {
      current = next.cloneNode(true);
      parent.insertBefore(current, cursor);
    } else {
      if (current !== cursor) parent.insertBefore(current, cursor);
      if (current.nodeType === 1) {
        for (const attr of Array.from(current.attributes)) {
          if (!next.hasAttribute(attr.name)) current.removeAttribute(attr.name);
        }
        for (const attr of Array.from(next.attributes)) {
          if (current.getAttribute(attr.name) !== attr.value) current.setAttribute(attr.name, attr.value);
        }
        patchChildren(current, next);
      } else if (current.nodeValue !== next.nodeValue) current.nodeValue = next.nodeValue;
    }
    cursor = current.nextSibling;
  }
  while (cursor) {
    const next = cursor.nextSibling;
    cursor.remove();
    cursor = next;
  }
}

export function renderSections(document, sections) {
  for (const [group, html] of Object.entries(sections)) {
    const template = document.createElement("template");
    template.innerHTML = html;
    patchChildren(document.getElementById(group), template.content);
  }
}
