import "server-only";

import { randomUUID } from "crypto";
import {
    MongoClient,
    type Db,
    type Document,
    type Filter,
} from "mongodb";

type DbRow = Record<string, unknown>;
type SelectOptions = { count?: "exact"; head?: boolean };
type DeleteOptions = { count?: "exact" };

type QueryError = {
    message: string;
    details?: string;
    hint?: string;
    code?: string;
};

type LooseQueryData = ReturnType<typeof JSON.parse>;

type QueryResult = {
    data: LooseQueryData;
    error: QueryError | null;
    count?: number | null;
};

type QueryMode = "select" | "insert" | "upsert" | "update" | "delete";
type FilterToken =
    | { type: "eq"; field: string; value: unknown }
    | { type: "in"; field: string; value: unknown[] }
    | { type: "is"; field: string; value: unknown }
    | { type: "contains"; field: string; value: DbRow };

declare global {
    var __cloudfinopsMongoClientPromise: Promise<MongoClient> | undefined;
}

function toQueryError(error: unknown): QueryError {
    if (error instanceof Error) {
        return { message: error.message };
    }

    return { message: "Unknown database error" };
}

function deepSerialize(value: unknown): unknown {
    if (value instanceof Date) {
        return value.toISOString();
    }

    if (Array.isArray(value)) {
        return value.map((item) => deepSerialize(item));
    }

    if (value && typeof value === "object") {
        const output: DbRow = {};
        for (const [key, item] of Object.entries(value as DbRow)) {
            output[key] = deepSerialize(item);
        }
        return output;
    }

    return value;
}

function normalizeDocument(document: Document): DbRow {
    const copy = { ...(document as DbRow), _id: (document as Document)._id as unknown };
    const mongoId = copy._id;
    delete copy._id;

    const normalized = deepSerialize(copy) as DbRow;
    if (!normalized.id && mongoId && typeof (mongoId as { toString?: () => string }).toString === "function") {
        normalized.id = (mongoId as { toString: () => string }).toString();
    }

    return normalized;
}

function normalizeProvider(value: unknown): string {
    const provider = String(value ?? "").trim().toLowerCase();
    if (provider === "aws" || provider === "azure" || provider === "gcp") {
        return provider;
    }
    throw new Error("provider must be explicitly set to one of: aws, azure, gcp");
}

function projectionFromColumns(columns: string | null): Document | undefined {
    if (!columns || columns.trim() === "*") {
        return undefined;
    }

    const projection: Document = { _id: 0 };
    for (const entry of columns.split(",")) {
        const column = entry.trim();
        if (column.length > 0) {
            projection[column] = 1;
        }
    }
    return projection;
}

function applyProjection(rows: DbRow[], columns: string | null): DbRow[] {
    if (!columns || columns.trim() === "*") {
        return rows;
    }

    const allowed = new Set(
        columns
            .split(",")
            .map((entry) => entry.trim())
            .filter(Boolean),
    );

    return rows.map((row) => {
        const projected: DbRow = {};
        for (const key of allowed) {
            if (Object.prototype.hasOwnProperty.call(row, key)) {
                projected[key] = row[key];
            }
        }
        return projected;
    });
}

function resolveMongoUri(explicitUrl?: string): string {
    if (explicitUrl && explicitUrl.startsWith("mongodb")) {
        return explicitUrl;
    }

    const value = process.env.MONGODB_URI;
    if (!value) {
        throw new Error("Missing MONGODB_URI");
    }
    return value;
}

function resolveMongoDbName(): string {
    return process.env.MONGODB_DB_NAME || "cloudfinops";
}

async function getDatabase(explicitUrl?: string): Promise<Db> {
    const uri = resolveMongoUri(explicitUrl);
    const dbName = resolveMongoDbName();

    if (!global.__cloudfinopsMongoClientPromise) {
        const client = new MongoClient(uri);
        global.__cloudfinopsMongoClientPromise = client.connect();
    }

    const client = await global.__cloudfinopsMongoClientPromise;
    return client.db(dbName);
}

class MongoQueryBuilder implements PromiseLike<QueryResult> {
    private mode: QueryMode | null = null;
    private filters: FilterToken[] = [];
    private selectColumns: string = "*";
    private returnColumns: string | null = null;
    private countRequested = false;
    private headMode = false;
    private deleteCountRequested = false;
    private limitValue: number | null = null;
    private sortEntries: Array<{ field: string; direction: 1 | -1 }> = [];
    private expectSingle = false;
    private payload: DbRow | DbRow[] | null = null;

    constructor(
        private readonly table: string,
        private readonly dbPromise: Promise<Db>,
    ) { }

    select(columns: string = "*", options?: SelectOptions): this {
        if (this.mode && this.mode !== "select") {
            this.returnColumns = columns;
            return this;
        }

        this.mode = "select";
        this.selectColumns = columns;
        this.countRequested = options?.count === "exact";
        this.headMode = options?.head === true;
        return this;
    }

    insert(data: DbRow | DbRow[]): this {
        this.mode = "insert";
        this.payload = data;
        return this;
    }

    upsert(data: DbRow | DbRow[]): this {
        this.mode = "upsert";
        this.payload = data;
        return this;
    }

    update(data: DbRow): this {
        this.mode = "update";
        this.payload = data;
        return this;
    }

    delete(options?: DeleteOptions): this {
        this.mode = "delete";
        this.deleteCountRequested = options?.count === "exact";
        return this;
    }

    eq(field: string, value: unknown): this {
        this.filters.push({ type: "eq", field, value });
        return this;
    }

    in(field: string, value: unknown[]): this {
        this.filters.push({ type: "in", field, value });
        return this;
    }

    is(field: string, value: unknown): this {
        this.filters.push({ type: "is", field, value });
        return this;
    }

    contains(field: string, value: DbRow): this {
        this.filters.push({ type: "contains", field, value });
        return this;
    }

    order(field: string, options?: { ascending?: boolean }): this {
        this.sortEntries.push({ field, direction: options?.ascending === false ? -1 : 1 });
        return this;
    }

    limit(value: number): this {
        this.limitValue = value;
        return this;
    }

    single(): this {
        this.expectSingle = true;
        return this;
    }

    private getRows(): DbRow[] {
        if (!this.payload) {
            return [];
        }

        return Array.isArray(this.payload) ? this.payload : [this.payload];
    }

    private prepareRow(row: DbRow): DbRow {
        const prepared = deepSerialize(row) as DbRow;
        if (this.table === "resources" || this.table === "cloud_integrations") {
            prepared.provider = normalizeProvider(prepared.provider);
        }
        if (typeof prepared.id !== "string" || prepared.id.length === 0) {
            prepared.id = randomUUID();
        }
        if (typeof prepared.created_at !== "string" || prepared.created_at.length === 0) {
            prepared.created_at = new Date().toISOString();
        }
        return prepared;
    }

    private buildQuery(): Filter<Document> {
        const query: Filter<Document> = {};
        for (const token of this.filters) {
            if (token.type === "eq") {
                query[token.field] = token.value as never;
                continue;
            }

            if (token.type === "is") {
                query[token.field] = token.value as never;
                continue;
            }

            if (token.type === "in") {
                query[token.field] = { $in: token.value } as never;
                continue;
            }

            for (const [nestedKey, nestedValue] of Object.entries(token.value)) {
                query[`${token.field}.${nestedKey}`] = nestedValue as never;
            }
        }
        return query;
    }

    private resolveUpsertFilter(row: DbRow): Filter<Document> {
        if (this.table === "resources" && row.integration_id && row.cloud_resource_id) {
            return {
                integration_id: row.integration_id as string,
                cloud_resource_id: row.cloud_resource_id as string,
            };
        }

        if (this.table === "governance_policies" && row.user_id && row.name) {
            return { user_id: row.user_id as string, name: row.name as string };
        }

        if (this.table === "dashboard_stats" && row.integration_id) {
            return { integration_id: row.integration_id as string };
        }

        if (this.table === "daily_spend_history" && row.integration_id && row.spend_date) {
            return {
                integration_id: row.integration_id as string,
                spend_date: row.spend_date as string,
            };
        }

        if (this.table === "waste_distribution" && row.integration_id && row.category_name) {
            return {
                integration_id: row.integration_id as string,
                category_name: row.category_name as string,
            };
        }

        if (row.id) {
            return { id: row.id as string };
        }

        return row as Filter<Document>;
    }

    private async executeSelect(): Promise<QueryResult> {
        const db = await this.dbPromise;
        const collection = db.collection(this.table);
        const query = this.buildQuery();

        if (this.headMode) {
            const count = await collection.countDocuments(query);
            return { data: null, error: null, count };
        }

        const count = this.countRequested ? await collection.countDocuments(query) : null;
        const projection = projectionFromColumns(this.selectColumns);
        let cursor = collection.find(query, { projection });

        if (this.sortEntries.length > 0) {
            const sort: Record<string, 1 | -1> = {};
            for (const entry of this.sortEntries) {
                sort[entry.field] = entry.direction;
            }
            cursor = cursor.sort(sort);
        }

        if (this.limitValue !== null) {
            cursor = cursor.limit(this.limitValue);
        }

        const rows = (await cursor.toArray()).map(normalizeDocument);
        const projected = applyProjection(rows, this.selectColumns);

        if (this.expectSingle) {
            if (projected.length === 0) {
                return {
                    data: null,
                    error: { message: "No rows found", code: "PGRST116" },
                    count: count ?? 0,
                };
            }
            return { data: projected[0], error: null, count: count ?? projected.length };
        }

        return { data: projected, error: null, count };
    }

    private async executeInsert(): Promise<QueryResult> {
        const db = await this.dbPromise;
        const collection = db.collection(this.table);
        const rows = this.getRows().map((row) => this.prepareRow(row));

        if (rows.length === 0) {
            return { data: [], error: null, count: 0 };
        }

        await collection.insertMany(rows, { ordered: false });
        const projected = applyProjection(rows, this.returnColumns);

        if (this.expectSingle) {
            return { data: projected[0] ?? null, error: null, count: projected.length };
        }

        return { data: projected, error: null, count: projected.length };
    }

    private async executeUpsert(): Promise<QueryResult> {
        const db = await this.dbPromise;
        const collection = db.collection(this.table);
        const rows = this.getRows().map((row) => this.prepareRow(row));
        const output: DbRow[] = [];

        for (const row of rows) {
            const now = new Date().toISOString();
            const filter = this.resolveUpsertFilter(row);
            const setPayload: DbRow = { ...row, updated_at: now };
            const insertPayload: DbRow = {
                created_at: (row.created_at as string) || now,
            };

            if (Object.prototype.hasOwnProperty.call(setPayload, "id")) {
                delete setPayload.id;
            }
            if (Object.prototype.hasOwnProperty.call(setPayload, "created_at")) {
                delete setPayload.created_at;
            }
            if (typeof row.id === "string" && row.id.length > 0) {
                insertPayload.id = row.id;
            }

            await collection.updateOne(
                filter,
                {
                    $set: setPayload,
                    $setOnInsert: insertPayload,
                },
                { upsert: true },
            );

            const doc = await collection.findOne(filter);
            if (doc) {
                output.push(normalizeDocument(doc));
            }
        }

        const projected = applyProjection(output, this.returnColumns);
        if (this.expectSingle) {
            return { data: projected[0] ?? null, error: null, count: projected.length };
        }
        return { data: projected, error: null, count: projected.length };
    }

    private async executeUpdate(): Promise<QueryResult> {
        const db = await this.dbPromise;
        const collection = db.collection(this.table);
        const query = this.buildQuery();
        const row = this.getRows()[0] ?? {};
        const payload = deepSerialize(row) as DbRow;

        if (Object.keys(payload).length === 0) {
            return { data: [], error: null, count: 0 };
        }

        if (this.table === "resources" || this.table === "cloud_integrations") {
            if (Object.prototype.hasOwnProperty.call(payload, "provider")) {
                payload.provider = normalizeProvider(payload.provider);
            }
        }

        payload.updated_at = new Date().toISOString();
        await collection.updateMany(query, { $set: payload });

        const docs = await collection
            .find(query, { projection: projectionFromColumns(this.returnColumns) })
            .toArray();
        const rows = docs.map(normalizeDocument);
        const projected = applyProjection(rows, this.returnColumns);

        if (this.expectSingle) {
            return { data: projected[0] ?? null, error: null, count: projected.length };
        }
        return { data: projected, error: null, count: projected.length };
    }

    private async executeDelete(): Promise<QueryResult> {
        const db = await this.dbPromise;
        const collection = db.collection(this.table);
        const query = this.buildQuery();
        const result = await collection.deleteMany(query);
        return {
            data: null,
            error: null,
            count: this.deleteCountRequested ? result.deletedCount : null,
        };
    }

    private async execute(): Promise<QueryResult> {
        const mode = this.mode ?? "select";
        if (mode === "select") {
            return this.executeSelect();
        }
        if (mode === "insert") {
            return this.executeInsert();
        }
        if (mode === "upsert") {
            return this.executeUpsert();
        }
        if (mode === "update") {
            return this.executeUpdate();
        }
        return this.executeDelete();
    }

    then<TResult1 = QueryResult, TResult2 = never>(
        onfulfilled?: ((value: QueryResult) => TResult1 | PromiseLike<TResult1>) | null,
        onrejected?: ((reason: unknown) => TResult2 | PromiseLike<TResult2>) | null,
    ): Promise<TResult1 | TResult2> {
        return this.execute()
            .catch((error: unknown) => {
                const queryError = toQueryError(error);
                console.error(`[MongoDBClient] ${this.table} ${this.mode ?? "select"} failed: ${queryError.message}`);
                return { data: null, error: queryError, count: null };
            })
            .then(onfulfilled, onrejected);
    }
}

class MongoDBClientWrapper {
    constructor(private readonly dbPromise: Promise<Db>) { }

    from(table: string): MongoQueryBuilder {
        return new MongoQueryBuilder(table, this.dbPromise);
    }
}

export type DatabaseClient = MongoDBClientWrapper;

export function createClient(url?: string, serviceKey?: string): DatabaseClient {
    void serviceKey;
    return new MongoDBClientWrapper(getDatabase(url));
}
