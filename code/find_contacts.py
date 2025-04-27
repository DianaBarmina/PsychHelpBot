from contacts import contacts_list
import re


def extract_score(score_text):
    if not score_text:
        return None

    match = re.search(r'(\d+)\s*балл', score_text.lower())
    if match:
        return int(match.group(1))

    return None


def extract_phq_info(phq_text: str) -> tuple[int | None, str | None]:
    if not phq_text:
        return None, None

    test_match = re.search(r'phq[-–]?(\d)', phq_text.lower())
    test_type = test_match.group(1) if test_match else None

    score_match = re.search(r'(\d+)\s*балл', phq_text.lower())
    score = int(score_match.group(1)) if score_match else None

    return score, test_type


def is_high_phq_score(phq_text: str) -> bool:
    score, test_type = extract_phq_info(phq_text)

    if score is None or test_type is None:
        return False

    if test_type == "2":
        return score >= 4
    elif test_type == "9":
        return score >= 15

    return False


def find_and_format_contacts(user_text: str,
                             emotions: list[str] = None,
                             phq_score: int = 0,
                             gad_score: int = 0,
                             max_contacts: int = 3,
                             ):
    relevant_contacts = []

    keywords = set()
    if user_text:
        keywords.update(user_text.lower().split())
    #if emotions:
    #    keywords.update([e.lower() for e in emotions])

    # Поиск по ключевым словам в issues и categories
    for contact in contacts_list:
        contact_keywords = set()
        contact_keywords.update([kw.lower() for kw in contact.get("issues", [])])
        contact_keywords.update([kw.lower() for kw in contact.get("categories", [])])

        if keywords & contact_keywords:
            relevant_contacts.append(contact)

    if phq_score is None:
        phq_score = -1
    else:
        phq_score = is_high_phq_score(phq_score)
    if gad_score is None:
        gad_score = -1
    else:
        gad_score = extract_score(gad_score)

    if phq_score or gad_score >= 15 or "суицид" in user_text.lower() or "селфхарм" in user_text.lower():
        for contact in contacts_list:
            crisis_match = any("суицид" in issue.lower() or "кризис" in cat.lower()
                               for issue in contact.get("issues", [])
                               for cat in contact.get("categories", []))
            if crisis_match and contact not in relevant_contacts:
                relevant_contacts.append(contact)

    relevant_contacts = relevant_contacts[:max_contacts]

    if not relevant_contacts:
        return ""

    formatted = "💬 Если нужна дополнительная поддержка, вы можете обратиться в следующие бесплатные службы:\n\n"
    for c in relevant_contacts:
        formatted += f"🔹 **{c['name']}**\n"
        formatted += f"🌐 Сайт: {c['website']}\n"
        formatted += f"📞 Телефон: {c['phone']}\n"
        if c.get("notes"):
            formatted += f"ℹ️ {c['notes']}\n"
        formatted += "\n"

    return formatted.strip()


def get_all_contacts_text(contacts: list) -> str:
    if not contacts:
        return "Контакты не найдены."

    response_lines = ["📚 Список доступных служб психологической помощи:\n"]

    for contact in contacts:
        lines = [f"🔹 *{contact['name']}*"]

        if contact.get("website"):
            lines.append(f"🌐 Сайт: {contact['website']}")

        lines.append(f"📞 Телефон: {contact['phone']}")

        if contact.get("issues"):
            issues = ", ".join(contact["issues"])
            lines.append(f"🧠 С чем работают: {issues}")

        if contact.get("notes"):
            lines.append(f"ℹ️ {contact['notes']}")

        lines.append("──────────────")
        response_lines.extend(lines)

    return "\n".join(response_lines)
