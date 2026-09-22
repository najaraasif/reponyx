export interface HealthResponse {
  status: string;
  service: string;
  version: string;
  environment: string;
}

export interface LLMHealthResponse {
  provider: string;
  model: string;
  available: boolean;
  status: string;
}

export interface Repository {
  id: string;
  url: string;
  status: string;
  created_at: string;
  analyzed_at: string | null;
}

export interface RepositoryAnalysis {
  repository_id: string;
  languages: Record<string, number>;
  package_managers: string[];
  entry_points: string[];
  test_locations: string[];
  framework_indicators: string[];
  symbols: SymbolInfo[];
  dependencies: DependencyInfo[];
  parse_failures: ParseFailure[];
  structure: DirectoryInfo;
}

export interface SymbolInfo {
  name: string;
  type: string;
  file_path: string;
  line_start: number;
  line_end: number;
}

export interface DependencyInfo {
  source: string;
  target: string;
  kind: string;
}

export interface ParseFailure {
  file_path: string;
  error: string;
}

export interface DirectoryInfo {
  name: string;
  type: string;
  children: DirectoryInfo[];
}

export interface Investigation {
  investigation_id: string;
  repository_id: string;
  status: string;
  issue: string;
  created_at: string;
}

export interface InvestigationDetail {
  investigation_id: string;
  repository_id: string;
  issue: string;
  status: string;
  current_step: string | null;
  iteration_count: number;
  errors: string[];
}

export interface InvestigationReport {
  issue: string;
  repository_id: string;
  summary: string;
  relevant_components: string[];
  evidence: EvidenceItem[];
  hypotheses: Hypothesis[];
  root_cause: string | null;
  supporting_evidence: string[];
  contradicting_evidence: string[];
  affected_files: string[];
  relevant_symbols: string[];
  dependencies: string[];
  confidence: string;
  limitations: string[];
  recommended_next_step: string;
}

export interface EvidenceItem {
  evidence_id: string;
  type: string;
  file_path: string;
  symbol: string | null;
  start_line: number | null;
  end_line: number | null;
  description: string;
  source_reference: string;
}

export interface Hypothesis {
  hypothesis_id: string;
  description: string;
  confidence: string;
  verification_status: string;
  supporting_evidence: string[];
  contradicting_evidence: string[];
}

export interface Repair {
  repair_id: string;
  repository_id: string;
  status: string;
  issue: string;
  iterations: number;
  created_at: string;
  completed_at: string | null;
}

export interface RepairReport {
  repair_id: string;
  status: string;
  issue: string;
  iterations: number;
  root_cause: string | null;
  repair_plan: string | null;
  changed_files: string[];
  test_results: TestResult[];
  failure_analysis: FailureAnalysis | null;
  repair_decision: string | null;
  final_report: string;
}

export interface TestResult {
  framework: string;
  passed: number;
  failed: number;
  skipped: number;
  duration: number;
  output: string;
}

export interface FailureAnalysis {
  failure_type: string;
  analysis: string;
  suggested_fix: string;
}

export interface RepairDiff {
  repair_id: string;
  diff: string;
}

export interface RepairReview {
  repair_id: string;
  status: string;
  report: {
    repair_id: string;
    repository_id: string;
    status: string;
    issue: string;
    iterations: number;
    changed_files: string[];
    test_results: TestResult[];
    verification_level: string;
    patch_description: string | null;
    final_report: string;
    root_cause: string | null;
  };
  diff: string | null;
}

export interface RepairHistoryItem {
  repair_id: string;
  repository_id: string;
  status: string;
  issue: string;
  iterations: number;
  created_at: string;
}

export interface SearchFilters {
  language?: string;
  file_path?: string;
  symbol_type?: string;
}

export interface SearchResult {
  file_path: string;
  line_range: [number, number];
  symbol_name: string;
  symbol_type: string;
  content: string;
  score: number;
  source: string;
}
