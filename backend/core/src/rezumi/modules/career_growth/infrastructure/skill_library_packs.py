"""Curated public course and lecture-note URLs grouped by skill family.

Entries are official platform pages or well-known public courses. This is not a
scrape of another roadmap site and is not a copy of a paid curriculum.
"""

from __future__ import annotations

import re
from urllib.parse import quote_plus

Resource = tuple[str, str, str]


def _yt(title: str, provider: str, video_id: str) -> Resource:
    return (title, provider, f"https://www.youtube.com/watch?v={video_id}")


def search_free(name: str) -> tuple[Resource, ...]:
    q = quote_plus(name)
    return (
        (
            f"{name} full courses on YouTube",
            "YouTube",
            f"https://www.youtube.com/results?search_query={q}+full+course",
        ),
        (
            f"{name} crash courses on YouTube",
            "YouTube",
            f"https://www.youtube.com/results?search_query={q}+crash+course",
        ),
        (
            f"{name} lecture notes on YouTube",
            "YouTube",
            f"https://www.youtube.com/results?search_query={q}+lecture+notes",
        ),
        (
            f"{name} on Khan Academy",
            "Khan Academy",
            f"https://www.khanacademy.org/search?page_search_query={q}",
        ),
        (
            f"{name} on freeCodeCamp",
            "freeCodeCamp",
            f"https://www.freecodecamp.org/news/search/?query={q}",
        ),
        (f"{name} on MIT OpenCourseWare", "MIT OCW", f"https://ocw.mit.edu/search/?q={q}"),
        (
            f"{name} on Microsoft Learn",
            "Microsoft Learn",
            f"https://learn.microsoft.com/en-us/search/?terms={q}",
        ),
        (
            f"{name} on edX (free audit options)",
            "edX",
            f"https://www.edx.org/search?q={q}",
        ),
        (
            f"{name} documentation on GitHub",
            "GitHub",
            f"https://github.com/search?q={q}+documentation&type=repositories",
        ),
    )


def search_paid(name: str) -> tuple[Resource, ...]:
    q = quote_plus(name)
    return (
        (f"{name} on Coursera", "Coursera", f"https://www.coursera.org/search?query={q}"),
        (
            f"{name} professional certificates on Coursera",
            "Coursera",
            f"https://www.coursera.org/search?query={q}&productTypeDescription=Professional%20Certificates",
        ),
        (f"{name} on Udemy", "Udemy", f"https://www.udemy.com/courses/search/?src=ukw&q={q}"),
        (
            f"{name} bootcamps on Udemy",
            "Udemy",
            f"https://www.udemy.com/courses/search/?src=ukw&q={q}+bootcamp",
        ),
        (f"{name} on edX", "edX", f"https://www.edx.org/search?q={q}"),
        (
            f"{name} on Udacity",
            "Udacity",
            f"https://www.udacity.com/catalog/all/best-match?search={q}",
        ),
    )


PACKS: dict[str, dict[str, tuple[Resource, ...]]] = {
    "algorithms": {
        "free": (
            _yt(
                "Algorithms and Data Structures Tutorial — Full Course",
                "YouTube / freeCodeCamp",
                "8hly31xKli0",
            ),
            _yt(
                "Data Structures Easy to Advanced Course",
                "YouTube / freeCodeCamp / William Fiset",
                "RBSGKlAvoiM",
            ),
            _yt(
                "Data Structures and Algorithms in Python — Full Course",
                "YouTube / freeCodeCamp",
                "pkYVOmU3MgA",
            ),
            _yt(
                "Data Structures — Computer Science Course for Beginners",
                "YouTube / freeCodeCamp",
                "zg9ih6SVACc",
            ),
            _yt(
                "Data Structures and Algorithms for Beginners",
                "YouTube / Programming with Mosh",
                "BBpAmxU_NQo",
            ),
            ("Harvard CS50 notes", "Harvard CS50", "https://cs50.harvard.edu/x/notes/"),
            (
                "MIT 6.006 Introduction to Algorithms",
                "MIT OCW",
                "https://ocw.mit.edu/courses/6-006-introduction-to-algorithms-spring-2020/",
            ),
            (
                "Khan Academy algorithms",
                "Khan Academy",
                "https://www.khanacademy.org/computing/computer-science/algorithms",
            ),
        ),
        "paid": (
            (
                "Algorithms Specialization",
                "Coursera / Stanford",
                "https://www.coursera.org/specializations/algorithms",
            ),
            (
                "Algorithms, Part I",
                "Coursera / Princeton",
                "https://www.coursera.org/learn/algorithms-part1",
            ),
            (
                "Data Structures and Algorithms on Udemy",
                "Udemy",
                "https://www.udemy.com/courses/search/?src=ukw&q=data+structures+and+algorithms",
            ),
            (
                "Python for Data Structures, Algorithms on Udemy",
                "Udemy",
                "https://www.udemy.com/courses/search/?src=ukw&q=python+data+structures+algorithms",
            ),
            (
                "CS50's Introduction to Computer Science",
                "edX / Harvard",
                "https://www.edx.org/learn/computer-science/harvard-university-cs50-s-introduction-to-computer-science",
            ),
        ),
    },
    "git": {
        "free": (
            _yt(
                "Git and GitHub for Beginners — Crash Course",
                "YouTube / freeCodeCamp",
                "RGOj5yH7evk",
            ),
            _yt("Complete Git and GitHub Tutorial", "YouTube / Kunal Kushwaha", "apGV9Kg7ics"),
            _yt(
                "Git Tutorial for Beginners: Learn Git in 1 Hour",
                "YouTube / Programming with Mosh",
                "8JJ101D3knE",
            ),
            _yt("Git for Professionals Tutorial", "YouTube / Tobias Günther", "Uszj_k0DGsg"),
            ("Pro Git book", "git-scm.com", "https://git-scm.com/book/en/v2"),
            ("Git documentation", "git-scm.com", "https://git-scm.com/doc"),
            ("GitHub Skills", "GitHub", "https://skills.github.com/"),
            (
                "Microsoft Learn Git",
                "Microsoft Learn",
                "https://learn.microsoft.com/en-us/training/paths/intro-to-git/",
            ),
        ),
        "paid": (
            (
                "Version Control with Git",
                "Coursera / Atlassian",
                "https://www.coursera.org/learn/version-control-with-git",
            ),
            ("Git on Coursera", "Coursera", "https://www.coursera.org/search?query=git"),
            (
                "Git and GitHub on Udemy",
                "Udemy",
                "https://www.udemy.com/courses/search/?src=ukw&q=git+github",
            ),
            (
                "Git complete guide on Udemy",
                "Udemy",
                "https://www.udemy.com/courses/search/?src=ukw&q=git+complete",
            ),
        ),
    },
    "testing": {
        "free": (
            _yt(
                "Intro To JavaScript Unit Testing and BDD",
                "YouTube / Traversy Media",
                "u5cLK1UrFyQ",
            ),
            (
                "MDN introducing tests",
                "MDN",
                "https://developer.mozilla.org/en-US/docs/Learn_web_development/Extensions/Testing",
            ),
            ("Playwright documentation", "Playwright", "https://playwright.dev/docs/intro"),
            ("Testing Library docs", "Testing Library", "https://testing-library.com/docs/"),
            ("Jest documentation", "Jest", "https://jestjs.io/docs/getting-started"),
            ("pytest documentation", "pytest", "https://docs.pytest.org/en/stable/"),
            (
                "Microsoft Learn unit testing",
                "Microsoft Learn",
                "https://learn.microsoft.com/en-us/dotnet/core/testing/unit-testing-best-practices",
            ),
        ),
        "paid": (
            (
                "Software Testing and Automation",
                "Coursera / University of Minnesota",
                "https://www.coursera.org/specializations/software-testing-automation",
            ),
            (
                "Software testing on Coursera",
                "Coursera",
                "https://www.coursera.org/search?query=software%20testing",
            ),
            (
                "Test automation on Udemy",
                "Udemy",
                "https://www.udemy.com/courses/search/?src=ukw&q=test+automation",
            ),
            (
                "Cypress and Playwright on Udemy",
                "Udemy",
                "https://www.udemy.com/courses/search/?src=ukw&q=cypress+playwright",
            ),
        ),
    },
    "system_design": {
        "free": (
            _yt("System Design for Beginners Course", "YouTube / freeCodeCamp", "m8Icp_Cid5o"),
            (
                "MIT 6.824 Distributed Systems",
                "MIT OCW / 6.824",
                "https://pdos.csail.mit.edu/6.824/",
            ),
            (
                "Microsoft Learn architecture",
                "Microsoft Learn",
                "https://learn.microsoft.com/en-us/azure/architecture/",
            ),
            ("AWS Architecture Center", "AWS", "https://aws.amazon.com/architecture/"),
            (
                "Google Cloud architecture framework",
                "Google Cloud",
                "https://cloud.google.com/architecture/framework",
            ),
            ("CNCF landscape", "CNCF", "https://www.cncf.io/archive/landscape/"),
        ),
        "paid": (
            (
                "Software Design and Architecture",
                "Coursera / University of Alberta",
                "https://www.coursera.org/specializations/software-design-architecture",
            ),
            (
                "Cloud architecture on Coursera",
                "Coursera",
                "https://www.coursera.org/search?query=system%20design",
            ),
            (
                "System design on Udemy",
                "Udemy",
                "https://www.udemy.com/courses/search/?src=ukw&q=system+design",
            ),
            (
                "Microservices on Udemy",
                "Udemy",
                "https://www.udemy.com/courses/search/?src=ukw&q=microservices+architecture",
            ),
        ),
    },
    "distributed": {
        "free": (
            ("MIT 6.824 Distributed Systems", "MIT PDOS", "https://pdos.csail.mit.edu/6.824/"),
            _yt("System Design for Beginners Course", "YouTube / freeCodeCamp", "m8Icp_Cid5o"),
            (
                "AWS Well-Architected reliability",
                "AWS",
                "https://docs.aws.amazon.com/wellarchitected/latest/reliability-pillar/welcome.html",
            ),
            ("Google SRE book", "Google SRE", "https://sre.google/sre-book/table-of-contents/"),
            ("Kafka documentation", "Apache Kafka", "https://kafka.apache.org/documentation/"),
        ),
        "paid": (
            (
                "Cloud Computing Specialization",
                "Coursera / University of Illinois",
                "https://www.coursera.org/specializations/cloud-computing",
            ),
            (
                "Distributed systems on Coursera",
                "Coursera",
                "https://www.coursera.org/search?query=distributed%20systems",
            ),
            (
                "Kafka and event-driven design on Udemy",
                "Udemy",
                "https://www.udemy.com/courses/search/?src=ukw&q=kafka+microservices",
            ),
            (
                "Distributed systems on Udemy",
                "Udemy",
                "https://www.udemy.com/courses/search/?src=ukw&q=distributed+systems",
            ),
        ),
    },
    "frontend": {
        "free": (
            _yt("HTML and CSS full course", "YouTube / freeCodeCamp", "G3e-cpL7ofc"),
            (
                "MDN Learn web development",
                "MDN",
                "https://developer.mozilla.org/en-US/docs/Learn_web_development",
            ),
            ("web.dev learn HTML", "web.dev", "https://web.dev/learn/html"),
            ("web.dev learn CSS", "web.dev", "https://web.dev/learn/css"),
            (
                "The Odin Project foundations",
                "The Odin Project",
                "https://www.theodinproject.com/paths/foundations/courses/foundations",
            ),
            ("W3C HTML", "W3C", "https://www.w3.org/html/"),
        ),
        "paid": (
            (
                "Meta Front-End Developer Professional Certificate",
                "Coursera / Meta",
                "https://www.coursera.org/professional-certificates/meta-front-end-developer",
            ),
            (
                "HTML, CSS, and JavaScript for Web Developers",
                "Coursera / Johns Hopkins",
                "https://www.coursera.org/learn/html-css-javascript-for-web-developers",
            ),
            (
                "HTML and CSS on Udemy",
                "Udemy",
                "https://www.udemy.com/courses/search/?src=ukw&q=html+css",
            ),
            (
                "Complete web developer bootcamp on Udemy",
                "Udemy",
                "https://www.udemy.com/courses/search/?src=ukw&q=web+developer+bootcamp",
            ),
        ),
    },
    "javascript": {
        "free": (
            _yt("JavaScript full course", "YouTube / freeCodeCamp", "PkZNo7MFNFg"),
            _yt(
                "JavaScript Tutorial for Beginners",
                "YouTube / Programming with Mosh",
                "W6NZfCO5SIk",
            ),
            _yt("TypeScript Course for Beginners", "YouTube / Academind", "BwuLxPH8IDs"),
            _yt("ReactJS Tutorial for Beginners", "YouTube / Programming with Mosh", "Ke90Tje7VS0"),
            (
                "MDN JavaScript guide",
                "MDN",
                "https://developer.mozilla.org/en-US/docs/Web/JavaScript/Guide",
            ),
            ("javascript.info", "javascript.info", "https://javascript.info/"),
            (
                "TypeScript handbook",
                "TypeScript",
                "https://www.typescriptlang.org/docs/handbook/intro.html",
            ),
            ("React documentation", "react.dev", "https://react.dev/learn"),
            ("Full Stack Open", "University of Helsinki", "https://fullstackopen.com/en/"),
        ),
        "paid": (
            (
                "Meta Front-End Developer Professional Certificate",
                "Coursera / Meta",
                "https://www.coursera.org/professional-certificates/meta-front-end-developer",
            ),
            (
                "Programming with JavaScript",
                "Coursera / Meta",
                "https://www.coursera.org/learn/programming-with-javascript",
            ),
            (
                "JavaScript and TypeScript on Udemy",
                "Udemy",
                "https://www.udemy.com/courses/search/?src=ukw&q=javascript+typescript",
            ),
            ("React on Udemy", "Udemy", "https://www.udemy.com/courses/search/?src=ukw&q=react+js"),
        ),
    },
    "accessibility": {
        "free": (
            (
                "MDN Accessibility",
                "MDN",
                "https://developer.mozilla.org/en-US/docs/Web/Accessibility",
            ),
            ("WAI-ARIA basics", "W3C WAI", "https://www.w3.org/WAI/ARIA/apg/"),
            ("web.dev accessible", "web.dev", "https://web.dev/learn/accessibility"),
            ("The A11Y Project", "A11Y Project", "https://www.a11yproject.com/"),
            ("WebAIM articles", "WebAIM", "https://webaim.org/articles/"),
            (
                "Web accessibility courses on YouTube",
                "YouTube",
                "https://www.youtube.com/results?search_query=web+accessibility+full+course",
            ),
        ),
        "paid": (
            (
                "Google UX Design Professional Certificate",
                "Coursera / Google",
                "https://www.coursera.org/professional-certificates/google-ux-design",
            ),
            (
                "Web accessibility on Coursera",
                "Coursera",
                "https://www.coursera.org/search?query=web%20accessibility",
            ),
            (
                "Accessibility on Udemy",
                "Udemy",
                "https://www.udemy.com/courses/search/?src=ukw&q=web+accessibility",
            ),
            (
                "Inclusive design on Udemy",
                "Udemy",
                "https://www.udemy.com/courses/search/?src=ukw&q=inclusive+design",
            ),
        ),
    },
    "databases": {
        "free": (
            _yt(
                "SQL Tutorial — Full Database Course for Beginners",
                "YouTube / freeCodeCamp",
                "HXV3zeQKqGY",
            ),
            _yt(
                "Database Systems — Cornell University Course",
                "YouTube / freeCodeCamp / Cornell",
                "4cWkVbC2bNE",
            ),
            _yt("MySQL Tutorial for Beginners", "YouTube / Programming with Mosh", "7S_tz1z_5bA"),
            (
                "Khan Academy Intro to SQL",
                "Khan Academy",
                "https://www.khanacademy.org/computing/computer-programming/sql",
            ),
            (
                "PostgreSQL documentation",
                "PostgreSQL",
                "https://www.postgresql.org/docs/current/tutorial.html",
            ),
            ("Use The Index, Luke", "Use The Index, Luke", "https://use-the-index-luke.com/"),
            ("Kaggle Intro to SQL", "Kaggle", "https://www.kaggle.com/learn/intro-to-sql"),
        ),
        "paid": (
            (
                "SQL for Data Science",
                "Coursera / UC Davis",
                "https://www.coursera.org/learn/sql-for-data-science",
            ),
            (
                "Databases and SQL for Data Science with Python",
                "Coursera / IBM",
                "https://www.coursera.org/learn/sql-data-science",
            ),
            ("SQL on Udemy", "Udemy", "https://www.udemy.com/courses/search/?src=ukw&q=sql"),
            (
                "PostgreSQL on Udemy",
                "Udemy",
                "https://www.udemy.com/courses/search/?src=ukw&q=postgresql",
            ),
        ),
    },
    "python": {
        "free": (
            _yt("Python for Everybody — full course", "YouTube / freeCodeCamp", "8DvywoWv6fI"),
            _yt(
                "Learn Python — Full Course for Beginners", "YouTube / freeCodeCamp", "rfscVS0vtbw"
            ),
            ("Python tutorial", "docs.python.org", "https://docs.python.org/3/tutorial/"),
            ("Kaggle Python", "Kaggle", "https://www.kaggle.com/learn/python"),
            (
                "pandas documentation",
                "pandas",
                "https://pandas.pydata.org/docs/getting_started/index.html",
            ),
            ("CS50 Python notes", "Harvard CS50", "https://cs50.harvard.edu/python/"),
        ),
        "paid": (
            (
                "Python for Everybody",
                "Coursera / University of Michigan",
                "https://www.coursera.org/specializations/python",
            ),
            (
                "Google IT Automation with Python",
                "Coursera / Google",
                "https://www.coursera.org/professional-certificates/google-it-automation",
            ),
            ("Python on Udemy", "Udemy", "https://www.udemy.com/courses/search/?src=ukw&q=python"),
            (
                "Python data science on Udemy",
                "Udemy",
                "https://www.udemy.com/courses/search/?src=ukw&q=python+data+science",
            ),
        ),
    },
    "ml": {
        "free": (
            _yt("Machine Learning for Everybody", "YouTube / freeCodeCamp", "i_LwzRVP7bg"),
            _yt("MIT Introduction to Deep Learning", "YouTube / MIT", "QDX-1M5Nj7s"),
            _yt("Machine Learning Course for Beginners", "YouTube / freeCodeCamp", "NWONeJKn6kc"),
            ("fast.ai Practical Deep Learning", "fast.ai", "https://course.fast.ai/"),
            (
                "scikit-learn user guide",
                "scikit-learn",
                "https://scikit-learn.org/stable/user_guide.html",
            ),
            (
                "Kaggle Intro to Machine Learning",
                "Kaggle",
                "https://www.kaggle.com/learn/intro-to-machine-learning",
            ),
            (
                "Google ML crash course",
                "Google",
                "https://developers.google.com/machine-learning/crash-course",
            ),
            ("PyTorch tutorials", "PyTorch", "https://pytorch.org/tutorials/"),
        ),
        "paid": (
            (
                "Machine Learning by Andrew Ng",
                "Coursera / Stanford",
                "https://www.coursera.org/learn/machine-learning",
            ),
            (
                "Deep Learning Specialization",
                "Coursera / DeepLearning.AI",
                "https://www.coursera.org/specializations/deep-learning",
            ),
            (
                "IBM Machine Learning Professional Certificate",
                "Coursera / IBM",
                "https://www.coursera.org/professional-certificates/ibm-machine-learning",
            ),
            (
                "Machine Learning on Udemy",
                "Udemy",
                "https://www.udemy.com/courses/search/?src=ukw&q=machine+learning",
            ),
            (
                "Deep Learning on Udemy",
                "Udemy",
                "https://www.udemy.com/courses/search/?src=ukw&q=deep+learning",
            ),
        ),
    },
    "llm": {
        "free": (
            ("Hugging Face NLP course", "Hugging Face", "https://huggingface.co/learn/nlp-course"),
            ("Hugging Face LLM course", "Hugging Face", "https://huggingface.co/learn/llm-course"),
            ("fast.ai", "fast.ai", "https://course.fast.ai/"),
            _yt("Machine Learning for Everybody", "YouTube / freeCodeCamp", "i_LwzRVP7bg"),
            (
                "Google generative AI",
                "Google",
                "https://developers.google.com/machine-learning/resources",
            ),
        ),
        "paid": (
            (
                "DeepLearning.AI short courses",
                "Coursera / DeepLearning.AI",
                "https://www.coursera.org/search?query=large%20language%20models",
            ),
            (
                "Generative AI on Coursera",
                "Coursera",
                "https://www.coursera.org/search?query=generative%20ai",
            ),
            (
                "LLM and LangChain on Udemy",
                "Udemy",
                "https://www.udemy.com/courses/search/?src=ukw&q=langchain+llm",
            ),
            (
                "Prompt engineering on Udemy",
                "Udemy",
                "https://www.udemy.com/courses/search/?src=ukw&q=prompt+engineering",
            ),
        ),
    },
    "data": {
        "free": (
            _yt(
                "Learn Data Science Tutorial — Full Course", "YouTube / freeCodeCamp", "ua-CiDNNj30"
            ),
            ("Kaggle Learn", "Kaggle", "https://www.kaggle.com/learn"),
            (
                "pandas getting started",
                "pandas",
                "https://pandas.pydata.org/docs/getting_started/index.html",
            ),
            (
                "Google Data Analytics overview",
                "Google",
                "https://grow.google/certificates/data-analytics/",
            ),
            (
                "Khan Academy statistics",
                "Khan Academy",
                "https://www.khanacademy.org/math/statistics-probability",
            ),
        ),
        "paid": (
            (
                "Google Data Analytics Professional Certificate",
                "Coursera / Google",
                "https://www.coursera.org/professional-certificates/google-data-analytics",
            ),
            (
                "IBM Data Science Professional Certificate",
                "Coursera / IBM",
                "https://www.coursera.org/professional-certificates/ibm-data-science",
            ),
            (
                "Data science on Udemy",
                "Udemy",
                "https://www.udemy.com/courses/search/?src=ukw&q=data+science",
            ),
            (
                "Tableau and Power BI on Udemy",
                "Udemy",
                "https://www.udemy.com/courses/search/?src=ukw&q=tableau+power+bi",
            ),
        ),
    },
    "statistics": {
        "free": (
            (
                "Khan Academy statistics",
                "Khan Academy",
                "https://www.khanacademy.org/math/statistics-probability",
            ),
            ("Seeing Theory", "Brown University", "https://seeing-theory.brown.edu/"),
            _yt(
                "Learn Data Science Tutorial — Full Course", "YouTube / freeCodeCamp", "ua-CiDNNj30"
            ),
            (
                "Kaggle intermediate ML",
                "Kaggle",
                "https://www.kaggle.com/learn/intermediate-machine-learning",
            ),
        ),
        "paid": (
            (
                "Statistics with Python",
                "Coursera / University of Michigan",
                "https://www.coursera.org/specializations/statistics-with-python",
            ),
            (
                "Business Statistics and Analysis",
                "Coursera / Rice",
                "https://www.coursera.org/specializations/business-statistics-analysis",
            ),
            (
                "Statistics on Udemy",
                "Udemy",
                "https://www.udemy.com/courses/search/?src=ukw&q=statistics",
            ),
            (
                "A/B testing on Udemy",
                "Udemy",
                "https://www.udemy.com/courses/search/?src=ukw&q=ab+testing",
            ),
        ),
    },
    "devops": {
        "free": (
            _yt("Docker Tutorial for Beginners", "YouTube / freeCodeCamp", "fqMOX6JJhGo"),
            _yt("Complete Docker Course", "YouTube / DevOps Directive", "RqTEHSBrYFw"),
            _yt("Kubernetes Course", "YouTube / freeCodeCamp", "d6WC5n9G_sM"),
            _yt("Introduction to Linux — Full Course", "YouTube / freeCodeCamp", "sWbUDq4S6Y8"),
            ("Docker docs", "Docker", "https://docs.docker.com/get-started/"),
            ("Kubernetes documentation", "Kubernetes", "https://kubernetes.io/docs/home/"),
            (
                "Terraform tutorials",
                "HashiCorp",
                "https://developer.hashicorp.com/terraform/tutorials",
            ),
            ("GitHub Actions docs", "GitHub", "https://docs.github.com/en/actions"),
        ),
        "paid": (
            ("DevOps on AWS", "Coursera / AWS", "https://www.coursera.org/search?query=devops"),
            (
                "IBM DevOps and Software Engineering",
                "Coursera / IBM",
                "https://www.coursera.org/professional-certificates/devops-and-software-engineering",
            ),
            (
                "Docker Kubernetes on Udemy",
                "Udemy",
                "https://www.udemy.com/courses/search/?src=ukw&q=docker+kubernetes",
            ),
            (
                "Terraform on Udemy",
                "Udemy",
                "https://www.udemy.com/courses/search/?src=ukw&q=terraform",
            ),
            (
                "CI/CD on Udemy",
                "Udemy",
                "https://www.udemy.com/courses/search/?src=ukw&q=cicd+jenkins+github+actions",
            ),
        ),
    },
    "linux": {
        "free": (
            _yt("Introduction to Linux — Full Course", "YouTube / freeCodeCamp", "sWbUDq4S6Y8"),
            _yt("Linux Operating System — Crash Course", "YouTube / freeCodeCamp", "ROjZy1WbCIA"),
            _yt("Computer Networking Course", "YouTube / freeCodeCamp", "qiQR5rTSshw"),
            ("Linux man-pages project", "man7.org", "https://man7.org/linux/man-pages/"),
            ("Ubuntu documentation", "Ubuntu", "https://ubuntu.com/tutorials"),
        ),
        "paid": (
            (
                "Google IT Support Professional Certificate",
                "Coursera / Google",
                "https://www.coursera.org/professional-certificates/google-it-support",
            ),
            (
                "Linux and UNIX on Coursera",
                "Coursera",
                "https://www.coursera.org/search?query=linux",
            ),
            (
                "Linux and networking on Udemy",
                "Udemy",
                "https://www.udemy.com/courses/search/?src=ukw&q=linux+networking",
            ),
            (
                "CompTIA Network+ on Udemy",
                "Udemy",
                "https://www.udemy.com/courses/search/?src=ukw&q=network%2B",
            ),
        ),
    },
    "cloud": {
        "free": (
            _yt("AWS Certified Cloud Practitioner Course", "YouTube / freeCodeCamp", "NhDYbskXRgc"),
            _yt("AWS Cloud Complete Bootcamp Course", "YouTube / freeCodeCamp", "zA8guDqfv40"),
            ("AWS documentation", "AWS", "https://docs.aws.amazon.com/index.html"),
            ("Google Cloud documentation", "Google Cloud", "https://cloud.google.com/docs"),
            (
                "Microsoft Learn Azure fundamentals",
                "Microsoft Learn",
                "https://learn.microsoft.com/en-us/training/azure/",
            ),
            (
                "AWS Well-Architected",
                "AWS",
                "https://aws.amazon.com/architecture/well-architected/",
            ),
        ),
        "paid": (
            (
                "AWS Cloud Solutions Architect",
                "Coursera / AWS",
                "https://www.coursera.org/professional-certificates/aws-cloud-solutions-architect",
            ),
            (
                "Google Cloud Digital Leader",
                "Coursera / Google Cloud",
                "https://www.coursera.org/search?query=google%20cloud",
            ),
            (
                "AWS on Udemy",
                "Udemy",
                "https://www.udemy.com/courses/search/?src=ukw&q=aws+certified",
            ),
            (
                "Azure on Udemy",
                "Udemy",
                "https://www.udemy.com/courses/search/?src=ukw&q=azure+fundamentals",
            ),
        ),
    },
    "security": {
        "free": (
            ("OWASP Top Ten", "OWASP", "https://owasp.org/www-project-top-ten/"),
            ("OWASP Cheat Sheet Series", "OWASP", "https://cheatsheetseries.owasp.org/"),
            (
                "PortSwigger Web Security Academy",
                "PortSwigger",
                "https://portswigger.net/web-security",
            ),
            ("MITRE ATT&CK", "MITRE", "https://attack.mitre.org/"),
            ("CWE list", "MITRE CWE", "https://cwe.mitre.org/"),
            (
                "Microsoft Learn security",
                "Microsoft Learn",
                "https://learn.microsoft.com/en-us/training/security/",
            ),
        ),
        "paid": (
            (
                "Google Cybersecurity Professional Certificate",
                "Coursera / Google",
                "https://www.coursera.org/professional-certificates/google-cybersecurity",
            ),
            (
                "IBM Cybersecurity Analyst",
                "Coursera / IBM",
                "https://www.coursera.org/professional-certificates/ibm-cybersecurity-analyst",
            ),
            (
                "Ethical hacking on Udemy",
                "Udemy",
                "https://www.udemy.com/courses/search/?src=ukw&q=ethical+hacking",
            ),
            (
                "Web application security on Udemy",
                "Udemy",
                "https://www.udemy.com/courses/search/?src=ukw&q=owasp+web+security",
            ),
        ),
    },
    "product": {
        "free": (
            ("SVPG articles", "Silicon Valley Product Group", "https://www.svpg.com/articles/"),
            ("Reforge essays", "Reforge", "https://www.reforge.com/blog"),
            ("Amplitude guides", "Amplitude", "https://amplitude.com/blog"),
            ("Mixpanel guides", "Mixpanel", "https://mixpanel.com/blog/"),
            (
                "Product management courses on YouTube",
                "YouTube",
                "https://www.youtube.com/results?search_query=product+management+full+course",
            ),
        ),
        "paid": (
            (
                "Google Project Management Professional Certificate",
                "Coursera / Google",
                "https://www.coursera.org/professional-certificates/google-project-management",
            ),
            (
                "Digital Product Management",
                "Coursera / University of Virginia",
                "https://www.coursera.org/specializations/uva-darden-digital-product-management",
            ),
            (
                "Product management on Udemy",
                "Udemy",
                "https://www.udemy.com/courses/search/?src=ukw&q=product+management",
            ),
            (
                "Product analytics on Udemy",
                "Udemy",
                "https://www.udemy.com/courses/search/?src=ukw&q=product+analytics",
            ),
        ),
    },
    "design": {
        "free": (
            (
                "Figma Learn",
                "Figma",
                "https://help.figma.com/hc/en-us/articles/14552701090327-Guide-to-Figma-for-beginners-tutorial",
            ),
            ("Material Design 3", "Google", "https://m3.material.io/"),
            ("NN/g articles", "Nielsen Norman Group", "https://www.nngroup.com/articles/"),
            (
                "Interaction Design Foundation open materials",
                "IDF",
                "https://www.interaction-design.org/literature",
            ),
            ("web.dev design", "web.dev", "https://web.dev/explore/design"),
        ),
        "paid": (
            (
                "Google UX Design Professional Certificate",
                "Coursera / Google",
                "https://www.coursera.org/professional-certificates/google-ux-design",
            ),
            (
                "CalArts UI/UX Design",
                "Coursera / CalArts",
                "https://www.coursera.org/specializations/ui-ux-design",
            ),
            (
                "UX design on Udemy",
                "Udemy",
                "https://www.udemy.com/courses/search/?src=ukw&q=ux+design",
            ),
            ("Figma on Udemy", "Udemy", "https://www.udemy.com/courses/search/?src=ukw&q=figma"),
        ),
    },
    "research": {
        "free": (
            (
                "NN/g research methods",
                "Nielsen Norman Group",
                "https://www.nngroup.com/topic/user-testing/",
            ),
            (
                "IDF research literature",
                "IDF",
                "https://www.interaction-design.org/literature/topics/user-research",
            ),
            (
                "Gov.uk service manual research",
                "GOV.UK",
                "https://www.gov.uk/service-manual/user-research",
            ),
        ),
        "paid": (
            (
                "Google UX Design Professional Certificate",
                "Coursera / Google",
                "https://www.coursera.org/professional-certificates/google-ux-design",
            ),
            (
                "User research on Coursera",
                "Coursera",
                "https://www.coursera.org/search?query=user%20research",
            ),
            (
                "User research on Udemy",
                "Udemy",
                "https://www.udemy.com/courses/search/?src=ukw&q=user+research",
            ),
            (
                "Interviewing users on Udemy",
                "Udemy",
                "https://www.udemy.com/courses/search/?src=ukw&q=user+interview",
            ),
        ),
    },
    "qa": {
        "free": (
            (
                "Ministry of Testing articles",
                "Ministry of Testing",
                "https://www.ministryoftesting.com/articles",
            ),
            ("Playwright docs", "Playwright", "https://playwright.dev/docs/intro"),
            (
                "OWASP testing guide",
                "OWASP",
                "https://owasp.org/www-project-web-security-testing-guide/",
            ),
            ("k6 documentation", "Grafana k6", "https://grafana.com/docs/k6/latest/"),
        ),
        "paid": (
            (
                "Software Testing and Automation",
                "Coursera / University of Minnesota",
                "https://www.coursera.org/specializations/software-testing-automation",
            ),
            (
                "ISTQB-oriented testing on Coursera",
                "Coursera",
                "https://www.coursera.org/search?query=software%20testing",
            ),
            (
                "Selenium and Playwright on Udemy",
                "Udemy",
                "https://www.udemy.com/courses/search/?src=ukw&q=selenium+playwright",
            ),
            (
                "Performance testing on Udemy",
                "Udemy",
                "https://www.udemy.com/courses/search/?src=ukw&q=jmeter+performance+testing",
            ),
        ),
    },
    "mobile": {
        "free": (
            _yt(
                "Android Development for Beginners — Full Course",
                "YouTube / freeCodeCamp",
                "fis26HvvDII",
            ),
            _yt("Flutter Course for Beginners", "YouTube / freeCodeCamp", "VPvVD8t02U8"),
            _yt("Kotlin Course — Tutorial for Beginners", "YouTube / freeCodeCamp", "F9UC9DY-vIU"),
            ("Android developer guides", "Android", "https://developer.android.com/guide"),
            (
                "Apple Human Interface Guidelines",
                "Apple",
                "https://developer.apple.com/design/human-interface-guidelines",
            ),
        ),
        "paid": (
            (
                "Meta Android Developer Professional Certificate",
                "Coursera / Meta",
                "https://www.coursera.org/professional-certificates/meta-android-developer",
            ),
            (
                "Meta iOS Developer Professional Certificate",
                "Coursera / Meta",
                "https://www.coursera.org/professional-certificates/meta-ios-developer",
            ),
            (
                "Flutter on Udemy",
                "Udemy",
                "https://www.udemy.com/courses/search/?src=ukw&q=flutter",
            ),
            (
                "React Native on Udemy",
                "Udemy",
                "https://www.udemy.com/courses/search/?src=ukw&q=react+native",
            ),
        ),
    },
    "management": {
        "free": (
            ("Manager Tools basics", "Manager Tools", "https://www.manager-tools.com/"),
            ("Google re:Work guides", "Google re:Work", "https://rework.withgoogle.com/en/guides"),
            (
                "Harvard Business Review",
                "HBR",
                "https://hbr.org/topic/subject/leadership-and-managing-people",
            ),
        ),
        "paid": (
            (
                "Google Project Management Professional Certificate",
                "Coursera / Google",
                "https://www.coursera.org/professional-certificates/google-project-management",
            ),
            (
                "Leading People and Teams",
                "Coursera / University of Michigan",
                "https://www.coursera.org/specializations/leading-teams",
            ),
            (
                "Engineering management on Udemy",
                "Udemy",
                "https://www.udemy.com/courses/search/?src=ukw&q=engineering+management",
            ),
            (
                "People management on Udemy",
                "Udemy",
                "https://www.udemy.com/courses/search/?src=ukw&q=people+management",
            ),
        ),
    },
    "business_analysis": {
        "free": (
            ("IIBA resources", "IIBA", "https://www.iiba.org/business-analysis-resources/"),
            (
                "Microsoft Learn Power BI",
                "Microsoft Learn",
                "https://learn.microsoft.com/en-us/training/powerplatform/power-bi",
            ),
            (
                "Khan Academy finance and capital markets",
                "Khan Academy",
                "https://www.khanacademy.org/economics-finance-domain",
            ),
        ),
        "paid": (
            (
                "Google Business Intelligence Professional Certificate",
                "Coursera / Google",
                "https://www.coursera.org/professional-certificates/google-business-intelligence",
            ),
            (
                "Business analysis on Coursera",
                "Coursera",
                "https://www.coursera.org/search?query=business%20analysis",
            ),
            (
                "Business analysis on Udemy",
                "Udemy",
                "https://www.udemy.com/courses/search/?src=ukw&q=business+analysis",
            ),
            (
                "Requirements gathering on Udemy",
                "Udemy",
                "https://www.udemy.com/courses/search/?src=ukw&q=requirements+gathering",
            ),
        ),
    },
    "writing": {
        "free": (
            (
                "Google developer documentation style guide",
                "Google",
                "https://developers.google.com/style",
            ),
            (
                "Microsoft Writing Style Guide",
                "Microsoft Learn",
                "https://learn.microsoft.com/en-us/style-guide/welcome/",
            ),
            ("The Good Docs Project", "Good Docs Project", "https://www.thegooddocsproject.dev/"),
            (
                "MDN contributing",
                "MDN",
                "https://developer.mozilla.org/en-US/docs/MDN/Community/Contributing/Getting_started",
            ),
        ),
        "paid": (
            (
                "Technical writing on Coursera",
                "Coursera",
                "https://www.coursera.org/search?query=technical%20writing",
            ),
            (
                "Google UX Design Professional Certificate",
                "Coursera / Google",
                "https://www.coursera.org/professional-certificates/google-ux-design",
            ),
            (
                "Technical writing on Udemy",
                "Udemy",
                "https://www.udemy.com/courses/search/?src=ukw&q=technical+writing",
            ),
            (
                "UX writing on Udemy",
                "Udemy",
                "https://www.udemy.com/courses/search/?src=ukw&q=ux+writing",
            ),
        ),
    },
    "project": {
        "free": (
            ("PMI knowledge center", "PMI", "https://www.pmi.org/learning/library"),
            ("Atlassian agile coach", "Atlassian", "https://www.atlassian.com/agile"),
            ("Scrum Guide", "Scrum.org", "https://www.scrum.org/resources/scrum-guide"),
        ),
        "paid": (
            (
                "Google Project Management Professional Certificate",
                "Coursera / Google",
                "https://www.coursera.org/professional-certificates/google-project-management",
            ),
            (
                "Agile Development and Scrum",
                "Coursera",
                "https://www.coursera.org/learn/agile-development-and-scrum",
            ),
            (
                "PMP and project management on Udemy",
                "Udemy",
                "https://www.udemy.com/courses/search/?src=ukw&q=pmp+project+management",
            ),
            (
                "Scrum master on Udemy",
                "Udemy",
                "https://www.udemy.com/courses/search/?src=ukw&q=scrum+master",
            ),
        ),
    },
    "agile": {
        "free": (
            ("Scrum Guide", "Scrum.org", "https://www.scrum.org/resources/scrum-guide"),
            ("Agile Alliance resources", "Agile Alliance", "https://agilealliance.org/agile101/"),
            ("Atlassian agile coach", "Atlassian", "https://www.atlassian.com/agile"),
        ),
        "paid": (
            (
                "Agile Development and Scrum",
                "Coursera",
                "https://www.coursera.org/learn/agile-development-and-scrum",
            ),
            (
                "Google Project Management Professional Certificate",
                "Coursera / Google",
                "https://www.coursera.org/professional-certificates/google-project-management",
            ),
            (
                "Scrum and Agile on Udemy",
                "Udemy",
                "https://www.udemy.com/courses/search/?src=ukw&q=scrum+master",
            ),
            ("Kanban on Udemy", "Udemy", "https://www.udemy.com/courses/search/?src=ukw&q=kanban"),
        ),
    },
    "networking": {
        "free": (
            _yt("Computer Networking Course", "YouTube / freeCodeCamp", "qiQR5rTSshw"),
            _yt("Computer Networking Full Course", "YouTube / Kunal Kushwaha", "IPvYjXCsTg8"),
            ("Cloudflare Learning Center", "Cloudflare", "https://www.cloudflare.com/learning/"),
            ("IETF RFCs", "IETF", "https://www.rfc-editor.org/"),
        ),
        "paid": (
            (
                "Google IT Support Professional Certificate",
                "Coursera / Google",
                "https://www.coursera.org/professional-certificates/google-it-support",
            ),
            (
                "Computer communications on Coursera",
                "Coursera",
                "https://www.coursera.org/search?query=computer%20networking",
            ),
            (
                "Network+ on Udemy",
                "Udemy",
                "https://www.udemy.com/courses/search/?src=ukw&q=network%2B",
            ),
            ("CCNA on Udemy", "Udemy", "https://www.udemy.com/courses/search/?src=ukw&q=ccna"),
        ),
    },
    "support": {
        "free": (
            (
                "Google IT Support overview",
                "Google",
                "https://grow.google/certificates/it-support/",
            ),
            (
                "Microsoft Learn Windows support",
                "Microsoft Learn",
                "https://learn.microsoft.com/en-us/windows/",
            ),
            _yt("Introduction to Linux — Full Course", "YouTube / freeCodeCamp", "sWbUDq4S6Y8"),
        ),
        "paid": (
            (
                "Google IT Support Professional Certificate",
                "Coursera / Google",
                "https://www.coursera.org/professional-certificates/google-it-support",
            ),
            (
                "Customer service on Coursera",
                "Coursera",
                "https://www.coursera.org/search?query=customer%20service",
            ),
            (
                "IT support on Udemy",
                "Udemy",
                "https://www.udemy.com/courses/search/?src=ukw&q=it+support",
            ),
            (
                "Service desk on Udemy",
                "Udemy",
                "https://www.udemy.com/courses/search/?src=ukw&q=service+desk",
            ),
        ),
    },
    "sales": {
        "free": (
            ("HubSpot Sales Blog", "HubSpot", "https://blog.hubspot.com/sales"),
            ("Salesforce Trailhead", "Salesforce", "https://trailhead.salesforce.com/"),
            ("Gong labs", "Gong", "https://www.gong.io/resources/"),
        ),
        "paid": (
            (
                "Sales Training: Practical Sales Techniques",
                "Coursera",
                "https://www.coursera.org/search?query=sales",
            ),
            (
                "Salesforce Sales Operations",
                "Coursera / Salesforce",
                "https://www.coursera.org/search?query=salesforce",
            ),
            (
                "Sales on Udemy",
                "Udemy",
                "https://www.udemy.com/courses/search/?src=ukw&q=sales+training",
            ),
            (
                "Negotiation on Udemy",
                "Udemy",
                "https://www.udemy.com/courses/search/?src=ukw&q=negotiation",
            ),
        ),
    },
    "marketing": {
        "free": (
            ("HubSpot Marketing Blog", "HubSpot", "https://blog.hubspot.com/marketing"),
            ("Google Skillshop", "Google", "https://skillshop.withgoogle.com/"),
            (
                "Meta Blueprint",
                "Meta",
                "https://www.facebookblueprint.com/student/activity/catalog",
            ),
            ("Moz Beginner's Guide to SEO", "Moz", "https://moz.com/beginners-guide-to-seo"),
        ),
        "paid": (
            (
                "Google Digital Marketing & E-commerce",
                "Coursera / Google",
                "https://www.coursera.org/professional-certificates/google-digital-marketing-ecommerce",
            ),
            (
                "Meta Social Media Marketing",
                "Coursera / Meta",
                "https://www.coursera.org/professional-certificates/facebook-social-media-marketing",
            ),
            (
                "Digital marketing on Udemy",
                "Udemy",
                "https://www.udemy.com/courses/search/?src=ukw&q=digital+marketing",
            ),
            ("SEO on Udemy", "Udemy", "https://www.udemy.com/courses/search/?src=ukw&q=seo"),
        ),
    },
    "finance": {
        "free": (
            (
                "Khan Academy finance",
                "Khan Academy",
                "https://www.khanacademy.org/economics-finance-domain/core-finance",
            ),
            ("Investopedia academy articles", "Investopedia", "https://www.investopedia.com/"),
            ("SEC investor education", "SEC", "https://www.investor.gov/introduction-investing"),
        ),
        "paid": (
            (
                "Financial Markets",
                "Coursera / Yale",
                "https://www.coursera.org/learn/financial-markets-global",
            ),
            (
                "Wharton Business Financial Modeling",
                "Coursera / Wharton",
                "https://www.coursera.org/specializations/wharton-business-financial-modeling",
            ),
            (
                "Financial modeling on Udemy",
                "Udemy",
                "https://www.udemy.com/courses/search/?src=ukw&q=financial+modeling",
            ),
            (
                "Accounting on Udemy",
                "Udemy",
                "https://www.udemy.com/courses/search/?src=ukw&q=accounting",
            ),
        ),
    },
    "accounting": {
        "free": (
            (
                "Khan Academy accounting",
                "Khan Academy",
                "https://www.khanacademy.org/economics-finance-domain/core-finance/accounting-and-financial-statements",
            ),
            ("IFRS resources", "IFRS", "https://www.ifrs.org/"),
            (
                "Investopedia accounting",
                "Investopedia",
                "https://www.investopedia.com/accounting-4689828",
            ),
        ),
        "paid": (
            (
                "Wharton Bookkeeping and Accounting",
                "Coursera / Wharton",
                "https://www.coursera.org/search?query=accounting",
            ),
            (
                "Intuit Bookkeeping Professional Certificate",
                "Coursera / Intuit",
                "https://www.coursera.org/professional-certificates/intuit-bookkeeping",
            ),
            (
                "Accounting on Udemy",
                "Udemy",
                "https://www.udemy.com/courses/search/?src=ukw&q=bookkeeping+accounting",
            ),
            (
                "Month-end close on Udemy",
                "Udemy",
                "https://www.udemy.com/courses/search/?src=ukw&q=month+end+close",
            ),
        ),
    },
    "hr": {
        "free": (
            ("SHRM resources", "SHRM", "https://www.shrm.org/"),
            ("EEOC guidance", "EEOC", "https://www.eeoc.gov/"),
            ("U.S. Department of Labor", "DOL", "https://www.dol.gov/"),
        ),
        "paid": (
            (
                "Human Resource Management",
                "Coursera",
                "https://www.coursera.org/search?query=human%20resources",
            ),
            (
                "HRCI-aligned HR on Coursera",
                "Coursera",
                "https://www.coursera.org/search?query=shrm",
            ),
            (
                "HR management on Udemy",
                "Udemy",
                "https://www.udemy.com/courses/search/?src=ukw&q=human+resources",
            ),
            (
                "Employment law on Udemy",
                "Udemy",
                "https://www.udemy.com/courses/search/?src=ukw&q=employment+law",
            ),
        ),
    },
    "recruiting": {
        "free": (
            ("LinkedIn Talent Blog", "LinkedIn", "https://www.linkedin.com/business/talent/blog"),
            (
                "Google re:Work hiring",
                "Google re:Work",
                "https://rework.withgoogle.com/en/guides/hiring-decision-make",
            ),
        ),
        "paid": (
            (
                "Recruiting on Coursera",
                "Coursera",
                "https://www.coursera.org/search?query=recruiting",
            ),
            (
                "Talent acquisition on Coursera",
                "Coursera",
                "https://www.coursera.org/search?query=talent%20acquisition",
            ),
            (
                "Technical recruiting on Udemy",
                "Udemy",
                "https://www.udemy.com/courses/search/?src=ukw&q=technical+recruiting",
            ),
            (
                "Sourcing on Udemy",
                "Udemy",
                "https://www.udemy.com/courses/search/?src=ukw&q=recruiting+sourcing",
            ),
        ),
    },
    "operations": {
        "free": (
            ("ASQ resources", "ASQ", "https://asq.org/quality-resources"),
            (
                "MIT OCW operations management search",
                "MIT OCW",
                "https://ocw.mit.edu/search/?q=operations%20management",
            ),
        ),
        "paid": (
            (
                "Supply Chain Management",
                "Coursera / Rutgers",
                "https://www.coursera.org/specializations/supply-chain-management",
            ),
            (
                "Operations management on Coursera",
                "Coursera",
                "https://www.coursera.org/search?query=operations%20management",
            ),
            (
                "Lean Six Sigma on Udemy",
                "Udemy",
                "https://www.udemy.com/courses/search/?src=ukw&q=lean+six+sigma",
            ),
            (
                "Supply chain on Udemy",
                "Udemy",
                "https://www.udemy.com/courses/search/?src=ukw&q=supply+chain",
            ),
        ),
    },
    "architecture": {
        "free": (
            (
                "Microsoft Learn architecture",
                "Microsoft Learn",
                "https://learn.microsoft.com/en-us/azure/architecture/",
            ),
            ("AWS Architecture Center", "AWS", "https://aws.amazon.com/architecture/"),
            ("Thoughtworks Technology Radar", "Thoughtworks", "https://www.thoughtworks.com/radar"),
        ),
        "paid": (
            (
                "Software Design and Architecture",
                "Coursera / University of Alberta",
                "https://www.coursera.org/specializations/software-design-architecture",
            ),
            (
                "Enterprise architecture on Coursera",
                "Coursera",
                "https://www.coursera.org/search?query=software%20architecture",
            ),
            (
                "Software architecture on Udemy",
                "Udemy",
                "https://www.udemy.com/courses/search/?src=ukw&q=software+architecture",
            ),
            (
                "Integration patterns on Udemy",
                "Udemy",
                "https://www.udemy.com/courses/search/?src=ukw&q=enterprise+integration",
            ),
        ),
    },
}

_SKILL_FAMILIES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("algorithms", ("data structures", "algorithm", "live coding")),
    ("git", ("version control", "git")),
    ("llm", ("llm", "retrieval-augmented", "responsible ai", "prompt")),
    (
        "ml",
        (
            "machine learning",
            "deep learning",
            "model ",
            "ml pipeline",
            "drift",
            "ai evaluation",
            "feature store",
            "causal inference",
        ),
    ),
    ("python", ("python",)),
    ("statistics", ("statistic", "experiment design", "variance analysis", "experiment analysis")),
    (
        "data",
        (
            "data wrangling",
            "data pipeline",
            "etl",
            "data modeling",
            "data quality",
            "data visualization",
            "data storytelling",
            "data analysis",
            "funnel",
            "kpi",
            "analytics",
            "spreadsheet",
            "cohort",
            "warehouse",
        ),
    ),
    (
        "javascript",
        ("javascript", "typescript", "component architecture", "state management", "frontend data"),
    ),
    ("accessibility", ("accessibility",)),
    (
        "frontend",
        (
            "html",
            "css",
            "performance optimization",
            "platform ui",
            "typography",
            "brand system",
            "design-to-engineering",
            "responsive layout",
            "browser rendering",
            "forms and validation",
            "internationalization",
        ),
    ),
    ("testing", ("testing", "test case", "test automation", "debugging", "code quality")),
    ("qa", ("bug reporting", "load testing", "performance and load", "exploratory testing")),
    (
        "distributed",
        (
            "distributed",
            "message queue",
            "caching",
            "scalability",
            "event-driven",
            "streaming vs batch",
        ),
    ),
    (
        "system_design",
        (
            "system design",
            "api design",
            "api contract",
            "deployment",
            "http and how the web",
            "pagination",
            "schema migration",
        ),
    ),
    (
        "databases",
        (
            "sql",
            "relational",
            "schema",
            "backup",
            "query performance",
            "replication",
            "database query",
        ),
    ),
    ("linux", ("linux", "networking basics", "command line", "ide and editor")),
    (
        "networking",
        ("tcp/ip", "routing", "firewall", "network", "dns and certificate", "switching"),
    ),
    (
        "cloud",
        ("cloud", "cost optimization", "cost-aware", "landing zone", "identity in the cloud"),
    ),
    (
        "devops",
        (
            "infrastructure as code",
            "ci/cd",
            "monitoring and alerting",
            "incident response",
            "kubernetes",
            "container",
            "observability",
            "sli",
            "slo",
            "progressive delivery",
        ),
    ),
    (
        "security",
        (
            "vulnerability",
            "threat modeling",
            "secure code",
            "forensics",
            "cloud security",
            "incident response and forensics",
            "authentication and authorization",
            "privacy and data",
            "identity and access",
            "secrets and configuration",
        ),
    ),
    ("mobile", ("offline-first", "app store", "battery", "push notification", "mobile security")),
    (
        "research",
        (
            "user research",
            "interviewing without",
            "synthesis and affinity",
            "research method",
            "research advocacy",
            "study design",
            "usability testing",
            "literature and baseline",
        ),
    ),
    (
        "design",
        (
            "interaction design",
            "design tool",
            "design system",
            "design critique",
            "microcopy",
            "prototyping",
            "journey mapping",
            "blueprinting",
        ),
    ),
    (
        "writing",
        (
            "information architecture",
            "docs-as-code",
            "subject-matter",
            "voice and tone",
            "content testing",
            "content governance",
            "editorial",
            "technical documentation",
            "plain language",
            "knowledge base",
            "application packaging",
            "job description",
        ),
    ),
    ("agile", ("agile", "impediment", "team metrics", "coaching without")),
    (
        "project",
        (
            "scope and timeline",
            "risk tracking",
            "cross-functional coordination",
            "status reporting",
            "change control",
            "budget tracking",
        ),
    ),
    (
        "architecture",
        (
            "requirements-to-architecture",
            "integration pattern",
            "non-functional",
            "architecture decision",
            "reading existing code",
            "object-oriented",
            "modular design",
            "estimating and scoping",
        ),
    ),
    (
        "product",
        (
            "product spec",
            "prioritization",
            "stakeholder",
            "metrics and analytics",
            "end-to-end feature",
            "onboarding design",
            "opportunity assessment",
            "roadmap communication",
            "working with product",
            "working with engineering",
        ),
    ),
    (
        "management",
        (
            "one-on-one",
            "technical planning",
            "performance management",
            "org design",
            "hiring",
            "mentoring",
            "behavioral interview",
            "evidence-backed interviewing",
        ),
    ),
    (
        "business_analysis",
        (
            "requirements gathering",
            "process mapping",
            "process documentation",
            "process improvement",
            "acceptance criteria",
            "systems analysis",
        ),
    ),
    (
        "support",
        (
            "ticket",
            "endpoint and identity",
            "customer communication under",
            "systematic troubleshooting",
            "product troubleshooting",
        ),
    ),
    (
        "sales",
        (
            "technical discovery",
            "product demonstration",
            "technical objection",
            "proof-of-concept",
            "discovery and qualification",
            "pipeline management",
            "negotiation and closing",
            "forecast accuracy",
            "account health",
            "outbound research",
            "qualification",
            "crm",
            "mutual action",
        ),
    ),
    (
        "marketing",
        (
            "positioning",
            "campaign",
            "audience and content",
            "channel-specific",
            "retention and lifecycle",
            "keyword",
            "on-page",
            "link building",
            "seo",
            "editorial planning",
            "content operations",
            "community moderation",
        ),
    ),
    (
        "finance",
        (
            "financial modeling",
            "business partnering",
            "valuation",
            "financial reporting",
            "variance analysis",
            "month-end",
            "double-entry",
            "reconciliation",
        ),
    ),
    ("accounting", ("double-entry", "month-end", "reconciliation", "bookkeeping")),
    (
        "hr",
        (
            "employment law",
            "employee relations",
            "hr data",
            "performance management systems",
            "org and manager coaching",
        ),
    ),
    (
        "recruiting",
        (
            "technical role and skill",
            "sourcing",
            "candidate experience",
            "offer negotiation",
            "intake and scorecard",
        ),
    ),
    (
        "operations",
        (
            "vendor and resource",
            "demand forecasting",
            "inventory",
            "supplier",
            "logistics",
            "logistics cost optimization",
            "operating cadence",
            "capacity and hiring",
            "calendar and priority",
        ),
    ),
    ("qa", ("qa",)),
)


def family_for_skill(name: str) -> str:
    key = name.casefold()
    best: tuple[int, str] | None = None
    for family, needles in _SKILL_FAMILIES:
        for needle in needles:
            if _needle_matches(key, needle) and (best is None or len(needle) > best[0]):
                best = (len(needle), family)
    return best[1] if best else "product"


def _needle_matches(key: str, needle: str) -> bool:
    token = needle.casefold().strip()
    if not token:
        return False
    if any(character in token for character in " /-"):
        return token in key
    return re.search(rf"(?<![a-z0-9]){re.escape(token)}(?![a-z0-9])", key) is not None


def extra_for_skill(name: str) -> tuple[tuple[Resource, ...], tuple[Resource, ...]]:
    """Skill-specific public pages layered on top of the family pack."""
    key = name.casefold()
    extras: dict[str, tuple[tuple[Resource, ...], tuple[Resource, ...]]] = {
        "data structures and algorithms": (
            (
                _yt(
                    "Data Structures and Algorithms Full Course",
                    "YouTube / Simplilearn",
                    "LcKqYoX8uH4",
                ),
                ("VisuAlgo", "VisuAlgo", "https://visualgo.net/en"),
            ),
            (("Algorithms on edX", "edX", "https://www.edx.org/search?q=algorithms"),),
        ),
        "relational databases": (
            (
                (
                    "PostgreSQL tutorial",
                    "PostgreSQL",
                    "https://www.postgresql.org/docs/current/tutorial.html",
                ),
            ),
            (),
        ),
        "sql": (
            (("Kaggle Intro to SQL", "Kaggle", "https://www.kaggle.com/learn/intro-to-sql"),),
            (),
        ),
        "machine learning and deep learning fundamentals": (
            (("DeepLearning.AI", "DeepLearning.AI", "https://www.deeplearning.ai/"),),
            (),
        ),
    }
    return extras.get(key, ((), ()))
