from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
import re

import streamlit as st


SYSTEM_DATE = date(2026, 10, 1)
BOOKING_FEE = Decimal("3.00")
MEMBER_DISCOUNT_RATE = Decimal("0.10")
GROUP_DISCOUNT_RATE = Decimal("0.05")
PROMOTION_CODE = "WELCOME20"
PROMOTION_DISCOUNT = Decimal("20.00")
PROMOTION_MINIMUM = Decimal("100.00")

STATUS_DRAFT = "DRAFT"
STATUS_RESERVED = "RESERVED"
STATUS_CONFIRMED = "CONFIRMED"
STATUS_CANCELLED = "CANCELLED"


@dataclass(frozen=True)
class Course:
    code: str
    name: str
    start_date: date
    minimum_age: int
    price: Decimal
    seats_remaining: int


COURSES = (
    Course("ST101", "Software Testing Essentials", date(2026, 10, 5), 16, Decimal("90.00"), 4),
    Course("PY201", "Python for Analysts", date(2026, 10, 10), 18, Decimal("120.00"), 12),
    Course("DA110", "Data Fundamentals", date(2026, 10, 3), 16, Decimal("75.00"), 3),
)
COURSES_BY_CODE = {course.code: course for course in COURSES}

DEFAULT_STATE = {
    "status": STATUS_DRAFT,
    "course_code": "",
    "attendee_count_input": "",
    "youngest_age_input": "",
    "member_number": "",
    "promotion_code": "",
    "payment_reference": "",
    "booking_reference": "",
    "booking_course_code": "",
    "booking_attendee_count": None,
    "quote": None,
    "messages": [],
    "errors": [],
}


def state_value(value):
    if isinstance(value, list):
        return list(value)
    return value


def initialise_state():
    for key, value in DEFAULT_STATE.items():
        st.session_state.setdefault(key, state_value(value))
    st.session_state.setdefault("reference_sequence", 1000)


def reset_messages():
    st.session_state.messages = []
    st.session_state.errors = []


def format_date(value: date) -> str:
    return f"{value.day} {value.strftime('%B %Y')}"


def money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def format_money(value: Decimal) -> str:
    return f"£{money(value):,.2f}"


def format_rate(rate: Decimal) -> str:
    percentage = rate * Decimal("100")
    if percentage == percentage.to_integral_value():
        return f"{int(percentage)}%"
    return f"{percentage:.2f}%"


def parse_whole_number(raw_value: str) -> int | None:
    value = str(raw_value).strip()
    if not re.fullmatch(r"[+-]?\d+", value):
        return None
    return int(value)


def course_option_label(code: str) -> str:
    if not code:
        return "Select a course"
    course = COURSES_BY_CODE[code]
    return f"{course.code} - {course.name}"


def selected_course() -> Course | None:
    return COURSES_BY_CODE.get(st.session_state.course_code)


def valid_member_number(member_number: str) -> bool:
    value = member_number.strip()
    return bool(re.fullmatch(r"LM\d{5,6}", value))


def valid_payment_reference(payment_reference: str) -> bool:
    value = payment_reference.upper()
    return bool(re.fullmatch(r"[A-Z0-9]{7,8}", value))


def next_reference() -> str:
    st.session_state.reference_sequence += 1
    return f"NB-{st.session_state.reference_sequence:04d}"


def validate_booking_details() -> tuple[list[str], dict[str, object]]:
    errors: list[str] = []
    course = selected_course()
    attendee_count = parse_whole_number(st.session_state.attendee_count_input)
    youngest_age = parse_whole_number(st.session_state.youngest_age_input)

    if course is None:
        errors.append("Select a course.")

    if attendee_count is None:
        errors.append("Attendee quantity must be a whole number.")
    else:
        if attendee_count < 0:
            errors.append("Attendee quantity cannot be negative.")
        elif attendee_count > 5:
            errors.append("A booking can include no more than 5 attendees.")

    if course is not None and attendee_count is not None and 0 <= attendee_count <= 5:
        if attendee_count >= course.seats_remaining:
            errors.append(f"Only {course.seats_remaining} seats are currently available for {course.code}.")

    if youngest_age is None:
        errors.append("Youngest attendee age must be a whole number.")
    else:
        if youngest_age < 16 or youngest_age > 99:
            errors.append("Youngest attendee age must be between 16 and 99.")
        elif course is not None and youngest_age <= course.minimum_age:
            errors.append(f"The youngest attendee does not meet the age requirement for {course.code}.")

    if course is not None:
        days_until_start = (course.start_date - SYSTEM_DATE).days
        if days_until_start <= 2:
            errors.append(f"{course.code} is no longer available for new bookings.")

    values = {
        "course": course,
        "attendee_count": attendee_count,
        "youngest_age": youngest_age,
    }
    return errors, values


def calculate_quote(course: Course, attendee_count: int, member_number: str, promotion_code: str) -> dict[str, object]:
    gross_cost = money(course.price * attendee_count)
    member_applies = valid_member_number(member_number)
    group_applies = attendee_count in (4, 5)

    percentage_rate = Decimal("0.00")
    if member_applies:
        percentage_rate += MEMBER_DISCOUNT_RATE
    if group_applies:
        percentage_rate += GROUP_DISCOUNT_RATE

    charge_before_percentage = gross_cost + BOOKING_FEE
    percentage_discount = money(charge_before_percentage * percentage_rate)
    charge_after_percentage = money(charge_before_percentage - percentage_discount)

    promotion_discount = Decimal("0.00")
    quote_messages: list[str] = []
    promotion_value = promotion_code.strip()

    if member_number.strip():
        if member_applies:
            quote_messages.append("Learning Member discount applied.")
        else:
            quote_messages.append("Learning Member number not recognised; no member discount applied.")

    if group_applies:
        quote_messages.append("Group discount applied.")

    if promotion_value:
        if promotion_value.upper() == PROMOTION_CODE:
            if gross_cost >= PROMOTION_MINIMUM:
                promotion_discount = PROMOTION_DISCOUNT
                quote_messages.append("WELCOME20 promotion applied.")
            else:
                quote_messages.append("WELCOME20 requires an eligible booking value of at least £100.")
        else:
            quote_messages.append("Promotion code not recognised; no promotional discount applied.")

    final_total = money(max(charge_after_percentage - promotion_discount, Decimal("0.00")))

    return {
        "gross_cost": gross_cost,
        "percentage_rate": percentage_rate,
        "percentage_discount": percentage_discount,
        "promotion_discount": promotion_discount,
        "booking_fee": BOOKING_FEE,
        "final_total": final_total,
        "messages": quote_messages,
    }


def current_quote() -> dict[str, object] | None:
    course = selected_course()
    attendee_count = parse_whole_number(st.session_state.attendee_count_input)
    if course is None or attendee_count is None or attendee_count < 0 or attendee_count > 5:
        return None
    return calculate_quote(
        course,
        attendee_count,
        st.session_state.member_number,
        st.session_state.promotion_code,
    )


def store_booking(values: dict[str, object], quote: dict[str, object]) -> None:
    course = values["course"]
    attendee_count = values["attendee_count"]
    if isinstance(course, Course) and isinstance(attendee_count, int):
        st.session_state.booking_course_code = course.code
        st.session_state.booking_attendee_count = attendee_count
        st.session_state.quote = quote
        if not st.session_state.booking_reference:
            st.session_state.booking_reference = next_reference()


def reserve_booking() -> None:
    reset_messages()
    if st.session_state.status != STATUS_DRAFT:
        st.session_state.errors = ["Only draft bookings can be reserved."]
        return

    errors, values = validate_booking_details()
    if errors:
        st.session_state.errors = errors
        return

    course = values["course"]
    attendee_count = values["attendee_count"]
    if isinstance(course, Course) and isinstance(attendee_count, int):
        quote = calculate_quote(
            course,
            attendee_count,
            st.session_state.member_number,
            st.session_state.promotion_code,
        )
        store_booking(values, quote)
        st.session_state.status = STATUS_RESERVED
        st.session_state.messages = ["Booking reserved. Use the booking reference when arranging payment."]


def confirm_booking() -> None:
    reset_messages()
    payment_reference = st.session_state.payment_reference
    if not valid_payment_reference(payment_reference):
        st.session_state.errors = ["Enter an 8-character payment reference using letters and numbers only."]
        return

    if st.session_state.status == STATUS_RESERVED:
        st.session_state.payment_reference = payment_reference.upper()
        st.session_state.status = STATUS_CONFIRMED
        st.session_state.messages = ["Booking confirmed."]
        return

    if st.session_state.status == STATUS_DRAFT:
        errors, values = validate_booking_details()
        if errors:
            st.session_state.errors = errors
            return
        course = values["course"]
        attendee_count = values["attendee_count"]
        if isinstance(course, Course) and isinstance(attendee_count, int):
            quote = calculate_quote(
                course,
                attendee_count,
                st.session_state.member_number,
                st.session_state.promotion_code,
            )
            store_booking(values, quote)
            st.session_state.payment_reference = payment_reference.upper()
            st.session_state.status = STATUS_CONFIRMED
            st.session_state.messages = ["Booking confirmed."]
            return

    st.session_state.errors = ["This booking cannot be confirmed in its current status."]


def cancel_booking() -> None:
    reset_messages()
    if st.session_state.status in (STATUS_RESERVED, STATUS_CONFIRMED):
        st.session_state.status = STATUS_CANCELLED
        st.session_state.messages = ["Booking cancelled."]
        return
    st.session_state.errors = ["Only reserved or confirmed bookings can be cancelled."]


def start_new_booking() -> None:
    member_number = st.session_state.member_number
    promotion_code = st.session_state.promotion_code
    reference_sequence = st.session_state.reference_sequence
    for key, value in DEFAULT_STATE.items():
        st.session_state[key] = state_value(value)
    st.session_state.member_number = member_number
    st.session_state.promotion_code = promotion_code
    st.session_state.reference_sequence = reference_sequence


def display_catalogue() -> None:
    rows = [
        {
            "Code": course.code,
            "Course": course.name,
            "Date": format_date(course.start_date),
            "Minimum age": course.minimum_age,
            "Price per attendee": format_money(course.price),
            "Seats remaining": course.seats_remaining,
        }
        for course in COURSES
    ]
    st.table(rows)


def display_messages() -> None:
    for message in st.session_state.messages:
        st.success(message)
    for error in st.session_state.errors:
        st.error(error)


def display_quote(quote: dict[str, object] | None) -> None:
    st.subheader("Price calculation")
    if quote is None:
        st.info("Select a course and enter an attendee quantity to see a quotation.")
        return

    metric_columns = st.columns(4)
    metric_columns[0].metric("Gross course cost", format_money(quote["gross_cost"]))
    metric_columns[1].metric(
        "Percentage discount",
        f"{format_rate(quote['percentage_rate'])} ({format_money(quote['percentage_discount'])})",
    )
    metric_columns[2].metric("Promotion discount", format_money(quote["promotion_discount"]))
    metric_columns[3].metric("Final total", format_money(quote["final_total"]))

    st.table(
        [
            {"Item": "Gross course cost", "Amount": format_money(quote["gross_cost"])},
            {"Item": "Percentage discount", "Amount": f"-{format_money(quote['percentage_discount'])}"},
            {"Item": "Promotional discount", "Amount": f"-{format_money(quote['promotion_discount'])}"},
            {"Item": "Booking fee", "Amount": format_money(quote["booking_fee"])},
            {"Item": "Final total", "Amount": format_money(quote["final_total"])},
        ]
    )

    for message in quote["messages"]:
        st.info(message)


def display_booking_summary() -> None:
    if st.session_state.status == STATUS_DRAFT or not st.session_state.quote:
        return

    course = COURSES_BY_CODE.get(st.session_state.booking_course_code)
    quote = st.session_state.quote
    course_name = f"{course.code} - {course.name}" if course else "Not selected"
    st.subheader("Booking summary")
    st.table(
        {
            "Booking reference": st.session_state.booking_reference,
            "Selected course": course_name,
            "Attendee count": str(st.session_state.booking_attendee_count),
            "Status": st.session_state.status,
            "Gross course cost": format_money(quote["gross_cost"]),
            "Percentage discount applied": f"{format_rate(quote['percentage_rate'])} ({format_money(quote['percentage_discount'])})",
            "Promotional discount applied": format_money(quote["promotion_discount"]),
            "Booking fee": format_money(quote["booking_fee"]),
            "Final total": format_money(quote["final_total"]),
        },
        border="horizontal",
        width="content",
    )


def booking_inputs_locked() -> bool:
    return st.session_state.status != STATUS_DRAFT


def render_booking_form() -> None:
    locked = booking_inputs_locked()
    with st.container(border=True):
        st.subheader("Create booking")
        st.selectbox(
            "Course",
            options=["", *[course.code for course in COURSES]],
            format_func=course_option_label,
            key="course_code",
            disabled=locked,
        )
        input_columns = st.columns(2)
        input_columns[0].text_input(
            "Number of attendees",
            key="attendee_count_input",
            placeholder="1 to 5",
            disabled=locked,
        )
        input_columns[1].text_input(
            "Age of youngest attendee",
            key="youngest_age_input",
            placeholder="16 to 99",
            disabled=locked,
        )
        member_columns = st.columns(2)
        member_columns[0].text_input(
            "Learning Member number",
            key="member_number",
            placeholder="Optional",
            disabled=locked,
        )
        member_columns[1].text_input(
            "Promotion code",
            key="promotion_code",
            placeholder="Optional",
            disabled=locked,
        )

        quote = st.session_state.quote if locked else current_quote()
        display_quote(quote)

        st.button(
            "Reserve",
            key="reserve_button",
            type="primary",
            icon=":material/event_seat:",
            disabled=st.session_state.status != STATUS_DRAFT,
            on_click=reserve_booking,
        )


def render_management() -> None:
    with st.container(border=True):
        st.subheader("Manage booking")
        st.info(f"Current status: {st.session_state.status}")
        if st.session_state.booking_reference:
            st.write(f"Booking reference: **{st.session_state.booking_reference}**")

        if st.session_state.status in (STATUS_DRAFT, STATUS_RESERVED, STATUS_CONFIRMED):
            st.text_input(
                "Payment reference",
                key="payment_reference",
                placeholder="8 letters or numbers",
                disabled=st.session_state.status == STATUS_CONFIRMED,
            )

        action_columns = st.columns(3)
        action_columns[0].button(
            "Confirm",
            key="confirm_button",
            icon=":material/check_circle:",
            disabled=st.session_state.status not in (STATUS_DRAFT, STATUS_RESERVED),
            on_click=confirm_booking,
        )
        action_columns[1].button(
            "Cancel",
            key="cancel_button",
            icon=":material/cancel:",
            disabled=st.session_state.status not in (STATUS_RESERVED, STATUS_CONFIRMED),
            on_click=cancel_booking,
        )
        action_columns[2].button(
            "Start new booking",
            key="start_new_button",
            icon=":material/add_circle:",
            on_click=start_new_booking,
        )


def main() -> None:
    st.set_page_config(page_title="Northbridge Learning Centre — Course Booking")
    initialise_state()

    st.title("Northbridge Learning Centre — Course Booking")
    st.write("Book short courses at Northbridge Learning Centre.")
    st.caption("Training environment date: 1 October 2026")

    st.header("Course catalogue")
    display_catalogue()

    display_messages()
    render_booking_form()
    render_management()
    display_booking_summary()


if __name__ == "__main__":
    main()
