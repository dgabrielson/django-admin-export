#####################################################################

from django.conf import settings
from django.template import Template
from django.utils.encoding import force_text
from django.utils.text import capfirst

#####################################################################


def safe_field_name(name):
    if ":" in name:
        name = name.split(":", 1)[0]
    return name


#####################################################################


def decode_field(fieldname):
    """
    actualname[:title[:none_str]]
    """
    if ":" not in fieldname:
        return fieldname, fieldname, ""
    colon_count = fieldname.count(":")

    if colon_count == 1:
        fieldname += ":"
    # just ignore more than three parts
    name, title, none_str = fieldname.split(":")[:3]
    if not title:
        title = name
    return name, title, none_str


#####################################################################


def default_latex_template(headers, fields):
    """
    Generate and return the default *compiled* template for LaTeX/PDF.
    """
    header_line = " & ".join(headers)
    column_spec = "l" * len(headers)
    orientation = "portrait" if len(headers) < 6 else "landscape"
    object_line = " & ".join(
        ["{{ object." + safe_field_name(f) + " }}" for f in fields]
    )
    return Template(
        r"""\documentclass[letterpaper,10pt]{article}


\usepackage{geometry}
\usepackage{longtable}
\usepackage{booktabs}
\usepackage{times}
\usepackage{fancyhdr}
\usepackage{relsize}
\usepackage[table]{xcolor}

\geometry{letterpaper,"""
        + orientation
        + r""",margin=1cm,bottom=1.5cm}

\pagestyle{fancy}


\lhead{}
\chead{}
\rhead{}
\lfoot{}
\cfoot{ {\footnotesize Generate on \today} }
\rfoot{}

\renewcommand{\headrulewidth}{0pt}
\renewcommand{\footrulewidth}{0pt}

\definecolor{light-gray}{gray}{0.9}
\begin{document}
\rowcolors{3}{white}{light-gray}
\relsize{-0.75}

\begin{longtable}{"""
        + column_spec
        + r"""}%
    \toprule
    """
        + header_line
        + r""" \\
    \midrule
    \endhead
    \bottomrule
    \endfoot
    {% for object in object_list %}%
        """
        + object_line
        + r""" \\
    {% endfor %}%
\end{longtable}

\end{document}
"""
    )


#####################################################################


def titlize(model, name):
    """
    Attempt to pull a meaningful title for this name.
    """
    if ":" in name:
        return name.split(":")[1]

    s = None
    if "." not in name:
        for f in model._meta.fields:
            if f.name == name:
                s = f.verbose_name
    if not s:
        s = name
        if "." in s:
            s = s.rsplit(".", 1)[1]
        s = s.replace("_", " ")

    return capfirst(s)


#####################################################################


def resolve_lookup(object, fieldname):
    """
    This function originally found in django.templates.base.py, modified
    for arbitrary nested field lookups.

    Performs resolution of a real variable against the given field name,
    i.e., this function returns the same as ``{{ object.name }}``  would
    in a template.
    """
    name, title, none_str = decode_field(fieldname)
    current = object
    try:  # catch-all for silent variable failures
        for bit in name.split("."):
            if current is None:
                return ""
            try:  # dictionary lookup
                current = current[bit]
            except (TypeError, AttributeError, KeyError, ValueError):
                try:  # attribute lookup
                    current = getattr(current, bit)
                except (TypeError, AttributeError):
                    try:  # list-index lookup
                        current = current[int(bit)]
                    except (
                        IndexError,  # list index out of range
                        ValueError,  # invalid literal for int()
                        KeyError,  # current is a dict without `int(bit)` key
                        TypeError,
                    ):  # unsubscriptable object
                        return "Failed lookup for key [%s] in %r" % (
                            bit,
                            current,
                        )  # missing attribute
            if callable(current):
                if getattr(current, "do_not_call_in_templates", False):
                    pass
                elif getattr(current, "alters_data", False):
                    current = "<< invalid -- no data alteration >>"
                else:
                    try:  # method call (assuming no args required)
                        current = current()
                    except TypeError:  # arguments *were* required
                        # GOTCHA: This will also catch any TypeError
                        # raised in the function itself.
                        current = (
                            settings.TEMPLATE_STRING_IF_INVALID
                        )  # invalid method call
    except Exception as e:
        if getattr(e, "silent_variable_failure", False):
            current = "<< invalid -- exception >>"
        else:
            raise

    if current is None and none_str is not None:
        current = none_str
    return force_text(current)


#####################################################################
