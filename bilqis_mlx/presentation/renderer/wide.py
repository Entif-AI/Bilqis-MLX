from __future__ import annotations

from .tables import WIDE_PANES, WIDE_ROW_FRACTIONS, WIDE_SEP
from .layout import _clean, _pane_widths

class WideView:
    def _wide_pane(self,names,width,body_height,height):
        """Stack each pane's sections without borrowing another pane's rows."""
        if not names:
            return [""]*body_height
        if len(names)==1:
            quotas={names[0]:min(len(self._section_rows(names[0])),body_height-2)}
        elif names[0]=='BRIDGE FAMILIES':
            # Concept totals are small: show each family once, then use all
            # remaining vertical space for distinct G/B grade results.
            slots=max(0,body_height-2*len(names))
            families=min(len(self._section_rows(names[0])),max(0,slots//3))
            grades=min(len(self._section_rows(names[1])),slots-families)
            families+=min(len(self._section_rows(names[0]))-families,
                          slots-families-grades)
            quotas={names[0]:families,names[1]:grades}
        else:
            slots=max(0,body_height-2*len(names))
            quotas={name:min(len(self.rows[name]),
                             max(1,round(height*WIDE_ROW_FRACTIONS[name])))
                    for name in names}
            # Small displays must still show every category's own heading.
            while sum(quotas.values())>slots:
                eligible=[name for name in names if quotas[name]>0]
                if not eligible:break
                biggest=max(eligible,key=lambda name:quotas[name])
                quotas[biggest]-=1
        lines=[]
        for name in names:
            lines.extend(self._wide_section(name,width,quotas[name]))
        return (lines+[""]*max(0,body_height-len(lines)))[:body_height]

    def _render_wide(self,headers,footer,*,width,height):
        widths=_pane_widths(width)
        tail=(1 if self.champion_line else 0)+(2 if footer is not None else 0)
        body_height=height-len(headers)-tail
        available=set(dict(self.tables))
        panes=[self._wide_pane(
                   tuple(name for name in names if name in available),
                   pane_width,body_height,height)
               for names,pane_width in zip(WIDE_PANES,widths)]
        lines=[_clean(header)[:width] for header in headers]
        for row in zip(*panes):
            line=WIDE_SEP.join(text.ljust(pane_width)
                               for text,pane_width in zip(row,widths))
            lines.append(line.rstrip())
        if self.champion_line:
            lines.append(_clean(self.champion_line)[:width])
        if footer is not None:
            lines.append("-"*width)
            lines.append(_clean(footer)[:width])
        return "\n".join(lines)
