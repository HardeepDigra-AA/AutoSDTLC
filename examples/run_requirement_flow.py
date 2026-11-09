"""Run a complete M3 requirement-to-test-coverage example in an in-memory database."""

from ai_sdlc.infrastructure.sqlite_repository import SQLiteRepository
from ai_sdlc.services.requirements_service import RequirementsService


def main() -> None:
    repository = SQLiteRepository(":memory:")
    repository.initialize()
    service = RequirementsService(repository)

    service.create_requirement(
        requirement_id="REQ-DEMO-001",
        title="Secure account login",
        description="Registered users sign in using valid credentials.",
        business_value="Protect user accounts and their information.",
        priority="high",
        created_by="REQUESTER-DEMO",
    )
    service.create_story(
        story_id="US-DEMO-001",
        requirement_id="REQ-DEMO-001",
        title="Sign in to an account",
        user_role="registered user",
        goal="to sign in with valid credentials",
        benefit="I can access my account securely",
        created_by="BA-01",
        actor_role="business_analyst",
    )
    service.add_acceptance_criterion(
        criterion_id="AC-DEMO-001",
        story_id="US-DEMO-001",
        description="Valid active-user credentials create an authenticated session.",
        created_by="BA-01",
        actor_role="business_analyst",
    )
    service.submit_for_ba_review(
        "REQ-DEMO-001", actor_id="BA-01", note="Story and AC reviewed.",
        actor_role="business_analyst",
    )
    service.approve_ba(
        "REQ-DEMO-001", actor_id="BA-01", note="BA review approved.",
        actor_role="business_analyst",
    )
    service.create_test_case(
        test_case_id="TC-DEMO-001",
        title="Valid active user can sign in",
        description="Submit a valid active-user credential pair and inspect the response.",
        test_level="api",
        created_by="QA-02",
        actor_role="qa_engineer",
        automation_reference="tests/api/test_login.py",
    )
    service.map_test_case(
        criterion_id="AC-DEMO-001",
        test_case_id="TC-DEMO-001",
        mapped_by="QA-02",
        actor_role="qa_engineer",
    )
    service.approve_po(
        "REQ-DEMO-001", actor_id="PO-01", note="Scope and test mapping approved.",
        actor_role="product_owner",
    )

    print(repository.get_requirement_brd("REQ-DEMO-001"))
    repository.close()


if __name__ == "__main__":
    main()
