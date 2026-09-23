"""FastAPI application entry point."""

from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from reponyx import __version__
from reponyx.config import Settings, get_settings
from reponyx.execution.service import ExecutionService
from reponyx.github.service import GitHubService, GitHubServiceError
from reponyx.investigation.service import InvestigationService
from reponyx.repair.ollama import OllamaStructuredProvider
from reponyx.repair.operations_service import RepairOperationsService
from reponyx.repair.service import RepairService
from reponyx.repositories.policy import RepositoryPolicyError
from reponyx.repositories.service import RepositoryService
from reponyx.repositories.workspace import WorkspaceError
from reponyx.retrieval.embeddings import build_embedding_provider
from reponyx.retrieval.models import RetrievalFilters
from reponyx.retrieval.service import RetrievalService
from reponyx.retrieval.store import VectorStore


class HealthResponse(BaseModel):
    """Stable response for process liveness checks."""

    status: str
    service: str
    version: str
    environment: str


class RepositoryCreateRequest(BaseModel):
    url: str = Field(min_length=1, max_length=500)


class RepositoryResponse(BaseModel):
    id: str
    url: str
    status: str


class RepositoryDetailResponse(RepositoryResponse):
    created_at: str
    analyzed_at: str | None


class SearchFilters(BaseModel):
    language: str | None = None
    file_path: str | None = None
    symbol_type: str | None = None


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2_000)
    top_k: int = Field(default=8, ge=1, le=50)
    filters: SearchFilters = Field(default_factory=SearchFilters)
    rerank: bool = False
    semantic_weight: float | None = Field(default=None, ge=0, le=1)
    lexical_weight: float | None = Field(default=None, ge=0, le=1)


class ContextRequest(SearchRequest):
    pass


class InvestigationRequest(BaseModel):
    issue: str = Field(min_length=1, max_length=10_000)


class TestExecutionRequest(BaseModel):
    framework: str = Field(min_length=1, max_length=32)
    timeout_seconds: float | None = Field(default=None, gt=0)


class RepairRequest(BaseModel):
    issue: str = Field(min_length=1, max_length=10_000)
    investigation_id: str | None = None
    primary_file: str = ""


def create_app(
    settings: Settings | None = None,
    repository_service: RepositoryService | None = None,
    retrieval_service: RetrievalService | None = None,
    investigation_service: InvestigationService | None = None,
    execution_service: ExecutionService | None = None,
    repair_service: RepairService | None = None,
    operations_service: RepairOperationsService | None = None,
) -> FastAPI:
    """Build the API application with injectable settings."""

    app = FastAPI(title="Reponyx", version=__version__)
    app_settings = settings or get_settings()
    cors_origins = [o.strip() for o in app_settings.cors_origins.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    service = repository_service
    retrieval = retrieval_service
    investigation = investigation_service
    execution = execution_service
    repair = repair_service
    operations = operations_service

    def current_settings() -> Settings:
        return app_settings

    def current_repository_service() -> RepositoryService:
        nonlocal service
        if service is None:
            service = RepositoryService(app_settings)
        return service

    SettingsDependency = Annotated[Settings, Depends(current_settings)]
    RepositoryDependency = Annotated[RepositoryService, Depends(current_repository_service)]

    def current_retrieval_service() -> RetrievalService:
        nonlocal retrieval
        if retrieval is not None:
            return retrieval
        repository_service = current_repository_service()
        vectors = VectorStore(repository_service.store)
        retrieval = RetrievalService(
            repository_service,
            vectors,
            build_embedding_provider(app_settings),
            app_settings.embedding_batch_size,
            app_settings.semantic_weight,
            app_settings.lexical_weight,
            app_settings.retrieval_character_budget,
        )
        return retrieval

    RetrievalDependency = Annotated[RetrievalService, Depends(current_retrieval_service)]

    def current_investigation_service() -> InvestigationService:
        nonlocal investigation
        if investigation is not None:
            return investigation
        investigation = InvestigationService(
            app_settings, current_repository_service(), current_retrieval_service()
        )
        return investigation

    InvestigationDependency = Annotated[
        InvestigationService, Depends(current_investigation_service)
    ]

    def current_execution_service() -> ExecutionService:
        nonlocal execution
        if execution is not None:
            return execution
        execution = ExecutionService(app_settings, current_repository_service())
        return execution

    ExecutionDependency = Annotated[ExecutionService, Depends(current_execution_service)]

    def current_repair_service() -> RepairService:
        nonlocal repair
        if repair is not None:
            return repair
        repair = RepairService(
            app_settings, current_repository_service(), current_execution_service()
        )
        return repair

    RepairDependency = Annotated[RepairService, Depends(current_repair_service)]

    def current_operations_service() -> RepairOperationsService:
        nonlocal operations
        if operations is not None:
            return operations
        operations = RepairOperationsService(current_repair_service())
        return operations

    OperationsDependency = Annotated[RepairOperationsService, Depends(current_operations_service)]

    @app.get("/healthz", response_model=HealthResponse, tags=["system"])
    def health(settings: SettingsDependency) -> HealthResponse:
        return HealthResponse(
            status="ok",
            service=settings.app_name,
            version=__version__,
            environment=settings.environment,
        )

    @app.get("/llm/health", tags=["system"])
    def llm_health() -> object:
        if app_settings.llm_provider == "ollama":
            return OllamaStructuredProvider(
                app_settings.ollama_base_url,
                app_settings.llm_model,
                app_settings.llm_timeout_seconds,
                app_settings.llm_max_output_tokens,
            ).health()
        return {
            "provider": app_settings.llm_provider,
            "model": app_settings.llm_model,
            "available": app_settings.llm_provider == "mock",
            "status": "configured"
            if app_settings.llm_provider == "mock"
            else "credential_required",
        }

    @app.post(
        "/repositories", response_model=RepositoryResponse, status_code=201, tags=["repositories"]
    )
    def create_repository(
        request: RepositoryCreateRequest, repositories: RepositoryDependency
    ) -> RepositoryResponse:
        try:
            return RepositoryResponse(**repositories.create(request.url))
        except RepositoryPolicyError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except WorkspaceError as exc:
            raise HTTPException(status_code=502, detail="repository clone failed") from exc

    @app.get("/repositories", response_model=list[RepositoryDetailResponse], tags=["repositories"])
    def list_repositories(repositories: RepositoryDependency) -> list[RepositoryDetailResponse]:
        return [RepositoryDetailResponse.model_validate(item) for item in repositories.list()]

    @app.get(
        "/repositories/{repository_id}",
        response_model=RepositoryDetailResponse,
        tags=["repositories"],
    )
    def get_repository(
        repository_id: str, repositories: RepositoryDependency
    ) -> RepositoryDetailResponse:
        item = repositories.get(repository_id)
        if item is None:
            raise HTTPException(status_code=404, detail="repository not found")
        return RepositoryDetailResponse.model_validate(item)

    @app.post("/repositories/{repository_id}/analyze", tags=["analysis"])
    def analyze_repository(
        repository_id: str, repositories: RepositoryDependency
    ) -> dict[str, object]:
        try:
            return repositories.analyze(repository_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="repository not found") from exc

    def section(repository_id: str, name: str, repositories: RepositoryService) -> object:
        try:
            return repositories.analysis_section(repository_id, name)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="analysis not found") from exc

    @app.get("/repositories/{repository_id}/structure", tags=["analysis"])
    def structure(repository_id: str, repositories: RepositoryDependency) -> object:
        return section(repository_id, "directories", repositories)

    @app.get("/repositories/{repository_id}/symbols", tags=["analysis"])
    def symbols(repository_id: str, repositories: RepositoryDependency) -> object:
        return section(repository_id, "symbols", repositories)

    @app.get("/repositories/{repository_id}/dependencies", tags=["analysis"])
    def dependencies(repository_id: str, repositories: RepositoryDependency) -> object:
        return section(repository_id, "dependencies", repositories)

    @app.post("/repositories/{repository_id}/index", tags=["retrieval"])
    def index_repository(repository_id: str, retrieval: RetrievalDependency) -> object:
        try:
            return retrieval.index(repository_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="analysis not found") from exc

    @app.get("/repositories/{repository_id}/index/status", tags=["retrieval"])
    def index_status(repository_id: str, retrieval: RetrievalDependency) -> object:
        try:
            return retrieval.status(repository_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="repository not found") from exc

    @app.get("/repositories/{repository_id}/index/is-indexed", tags=["retrieval"])
    def is_indexed(repository_id: str, retrieval: RetrievalDependency) -> object:
        return {"repository_id": repository_id, "indexed": retrieval.is_indexed(repository_id)}

    @app.post("/repositories/{repository_id}/search", tags=["retrieval"])
    def search_repository(
        repository_id: str, request: SearchRequest, retrieval: RetrievalDependency
    ) -> object:
        filters = RetrievalFilters(**request.filters.model_dump())
        try:
            return retrieval.search(
                repository_id,
                request.query,
                request.top_k,
                filters,
                request.rerank,
                request.semantic_weight,
                request.lexical_weight,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="repository not found") from exc

    @app.post("/repositories/{repository_id}/context", tags=["retrieval"])
    def context_repository(
        repository_id: str, request: ContextRequest, retrieval: RetrievalDependency
    ) -> object:
        filters = RetrievalFilters(**request.filters.model_dump())
        try:
            return retrieval.context(
                repository_id,
                request.query,
                request.top_k,
                filters,
                request.rerank,
                request.semantic_weight,
                request.lexical_weight,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="repository not found") from exc

    @app.get("/investigations", tags=["investigations"])
    def list_investigations(investigations: InvestigationDependency) -> object:
        return investigations.list()

    @app.post("/repositories/{repository_id}/investigations", tags=["investigations"])
    def create_investigation(
        repository_id: str,
        request: InvestigationRequest,
        investigations: InvestigationDependency,
    ) -> object:
        try:
            return investigations.create(repository_id, request.issue)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="repository not found") from exc

    @app.get("/investigations/{investigation_id}", tags=["investigations"])
    def get_investigation(investigation_id: str, investigations: InvestigationDependency) -> object:
        result = investigations.get(investigation_id)
        if result is None:
            raise HTTPException(status_code=404, detail="investigation not found")
        return result

    @app.get("/investigations/{investigation_id}/report", tags=["investigations"])
    def get_investigation_report(
        investigation_id: str, investigations: InvestigationDependency
    ) -> object:
        result = investigations.report(investigation_id)
        if result is None:
            raise HTTPException(status_code=404, detail="investigation report not found")
        return result

    @app.post("/repositories/{repository_id}/tests", tags=["execution"])
    def run_tests(
        repository_id: str,
        request: TestExecutionRequest,
        executions: ExecutionDependency,
    ) -> object:
        try:
            return executions.run_tests(repository_id, request.framework, request.timeout_seconds)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="repository not found") from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.post("/repositories/{repository_id}/executions", tags=["execution"])
    def create_execution(
        repository_id: str,
        request: TestExecutionRequest,
        executions: ExecutionDependency,
    ) -> object:
        return run_tests(repository_id, request, executions)

    @app.get("/executions/{execution_id}", tags=["execution"])
    def get_execution(execution_id: str, executions: ExecutionDependency) -> object:
        result = executions.get(execution_id)
        if result is None:
            raise HTTPException(status_code=404, detail="execution not found")
        return result

    @app.get("/executions/{execution_id}/results", tags=["execution"])
    def get_execution_result(execution_id: str, executions: ExecutionDependency) -> object:
        result = executions.get(execution_id)
        if result is None:
            raise HTTPException(status_code=404, detail="execution not found")
        return result

    @app.post("/repositories/{repository_id}/repairs", tags=["repairs"])
    def create_repair(
        repository_id: str, request: RepairRequest, repairs: RepairDependency
    ) -> object:
        try:
            return repairs.create(
                repository_id,
                request.issue,
                request.investigation_id,
                primary_file=request.primary_file,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="repository not found") from exc

    @app.get("/repairs/{repair_id}", tags=["repairs"])
    def get_repair(repair_id: str, repairs: RepairDependency) -> object:
        result = repairs.get(repair_id)
        if result is None:
            raise HTTPException(status_code=404, detail="repair not found")
        return result

    @app.get("/repairs/{repair_id}/report", tags=["repairs"])
    def get_repair_report(repair_id: str, repairs: RepairDependency) -> object:
        result = repairs.report(repair_id)
        if result is None:
            raise HTTPException(status_code=404, detail="repair report not found")
        return result

    @app.get("/repairs/{repair_id}/diff", tags=["repairs"])
    def get_repair_diff(repair_id: str, repairs: RepairDependency) -> object:
        result = repairs.diff(repair_id)
        if result is None:
            return {"repair_id": repair_id, "diff": ""}
        return {"repair_id": repair_id, "diff": result}

    @app.post("/repairs/{repair_id}/cancel", tags=["repairs"])
    def cancel_repair(repair_id: str, repairs: RepairDependency) -> object:
        try:
            return repairs.cancel(repair_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="repair not found") from exc

    @app.get("/repairs", tags=["repairs"])
    def repair_history(
        operations: OperationsDependency, repository_id: str | None = None
    ) -> object:
        return operations.history(repository_id)

    @app.get("/repairs/{repair_id}/review", tags=["repairs"])
    def repair_review(repair_id: str, operations: OperationsDependency) -> object:
        try:
            return operations.review(repair_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="repair not found") from exc

    @app.post("/repairs/{repair_id}/approve", tags=["repairs"])
    def approve_repair(repair_id: str, operations: OperationsDependency) -> object:
        try:
            return operations.approve(repair_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="repair not found") from exc

    @app.post("/repairs/{repair_id}/reject", tags=["repairs"])
    def reject_repair(repair_id: str, operations: OperationsDependency) -> object:
        try:
            return operations.reject(repair_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="repair not found") from exc

    @app.post("/repairs/{repair_id}/create-pr", tags=["github"])
    def create_pull_request(
        repair_id: str,
        repairs: RepairDependency,
        repositories: RepositoryDependency,
    ) -> object:
        report = repairs.report(repair_id)
        if report is None:
            raise HTTPException(status_code=404, detail="repair not found")
        if report.get("status") != "completed":
            raise HTTPException(
                status_code=422,
                detail="PR creation requires a completed repair with passing tests",
            )
        repo = repositories.store.get(report.get("repository_id", ""))
        if repo is None:
            raise HTTPException(status_code=404, detail="repository not found")
        settings = get_settings()
        if not settings.github_token:
            raise HTTPException(
                status_code=503,
                detail="GitHub integration not configured. Set GITHUB_TOKEN environment variable.",
            )
        workspace = Path(repo.workspace_path)
        if not workspace.exists():
            raise HTTPException(
                status_code=503,
                detail="Repository workspace not found on disk.",
            )
        try:
            github = GitHubService(settings)
            result = github.create_pull_request(
                workspace_path=workspace,
                repository_url=repo.url,
                issue_title=report.get("issue", "")[:200],
                issue_body=report.get("issue", ""),
                diff=report.get("final_diff", ""),
                changed_files=report.get("changed_files", []),
                repair_id=repair_id,
                root_cause=report.get("root_cause"),
                confidence=report.get("confidence", "low"),
            )
            return {
                "pr_url": result.pr_url,
                "pr_number": result.pr_number,
                "branch_name": result.branch_name,
                "commit_sha": result.commit_sha,
                "repository": result.repository,
            }
        except GitHubServiceError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    return app


app = create_app()
