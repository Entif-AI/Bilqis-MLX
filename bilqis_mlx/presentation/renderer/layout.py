from __future__ import annotations

from .tables import Column, WIDE_PANES, WIDE_SEP

def _clean(value):
    return str(value if value is not None else "-").replace("\n", " ").encode(
        "ascii", "replace").decode("ascii")



def _step_exam(step,attempt):
    return f"{_clean(step)}/{_clean(attempt)}"



def _cell(value, width, *, right=False):
    text = _clean(value)
    if len(text) > width:
        text = text[:width - 1] + "~" if width > 1 else "~"
    return text.rjust(width) if right else text.ljust(width)



def _human_duration(seconds):
    value=max(0,int(seconds))
    days,value=divmod(value,86400)
    hours,value=divmod(value,3600)
    minutes,seconds=divmod(value,60)
    parts=[]
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    if seconds or not parts:
        parts.append(f"{seconds}s")
    return " ".join(parts)



def _header_table(fields):
    headings=" ".join(
        _cell(label,width) for label,_value,width,_right in fields).rstrip()
    values=" ".join(
        _cell(value,width,right=right)
        for _label,value,width,right in fields).rstrip()
    return headings,values



def _columns(specs, width):
    """Choose and shrink columns without wrapping or erasing core semantics."""
    chosen = [s for s in specs if not s.optional]
    for item in specs:
        if item.optional and (sum(s.width for s in chosen) + len(chosen) + item.width <= width):
            chosen.append(item)
    chosen = [s for s in specs if s in chosen]
    # Narrow windows discard low-priority metrics before clipping the decision.
    while (sum(s.width for s in chosen) + len(chosen) - 1 > width and
           len(chosen) > 2):
        drop = next((c for c in reversed(chosen) if c.optional), None)
        if drop is None:
            drop = next((c for c in reversed(chosen) if c.key not in
                         ("grade", "decision", "outcome", "detail",
                          "right_pct", "subject", "step_exam",
                          "score_line", "right_grew", "result")),None)
        if drop is None:break
        chosen.remove(drop)
    if sum(s.width for s in chosen) + len(chosen) - 1 > width:
        overflow = sum(s.width for s in chosen) + len(chosen) - 1 - width
        biggest = max(chosen, key=lambda c: c.width)
        chosen = [Column(c.name,max(4,c.width-overflow),c.key,c.optional,c.right)
                  if c is biggest else c for c in chosen]
    return chosen



def _table_line(row, columns):
    return " ".join(_cell(row.get(column.key,"-"),column.width,
                          right=column.right) for column in columns).rstrip()



def _section_heading(name,label):
    return label if name=="GRADES & MASTERY" else f"{name}   [{label}]"



def _right_header(left,summary,width):
    """Keep the means visible on short windows, without hidden line wrapping."""
    if len(summary)>width-2:return summary[:width]
    left=left[:max(0,width-len(summary)-2)]
    return left+' '*max(2,width-len(left)-len(summary))+summary



def _pane_widths(width):
    """Share real terminal columns without virtual wrapping or lost space."""
    free = width - len(WIDE_SEP) * (len(WIDE_PANES)-1)
    if free < 270:
        # The compact letter-school tables make a 210-column window viable:
        # candidate evidence stays broad, the middle pane keeps its live core,
        # and mastery receives enough room for a meaningful outcome label.
        gain=max(0,free-204)
        left=86+gain*33//66
        middle=54+gain*22//66
    else:
        gain=free-270
        left=119+gain//2
        middle=76+gain//4
    return left,middle,free-left-middle



def _wide_columns(specs,width):
    """Give extra space to the text field rather than truncating its meaning."""
    columns=_columns(specs,width)
    unused=width-(sum(c.width for c in columns)+len(columns)-1)
    if unused<=0:return columns
    target=next((c.key for c in columns if c.key in
                 ("decision","outcome","detail","family")),None)
    if target is None:return columns
    return [Column(c.name,c.width+unused if c.key==target else c.width,
                   c.key,c.optional,c.right) for c in columns]
