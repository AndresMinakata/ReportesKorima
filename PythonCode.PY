import pyodbc
import os
import csv
from datetime import datetime
import subprocess as sp
Server =  input("Servidor...  \n")
"\n"
Database = input("Base de datos...  \n")
"\n"
User = input("Usuario...  \n")
"\n"
Password = input("Contraseña...  \n")
"\n"
# ODBC connection string
connectionString =( 
    f"DRIVER={{ODBC Driver 18 for SQL Server}};"
    f"SERVER={Server};"
    f"DATABASE={Database};"
    f"UID={User};"
    f"PWD={Password};"
    f"TrustServerCertificate=yes;"
)
try:
    # Establish connection
    connection = pyodbc.connect(connectionString)
    print("Conexión exitosa")
    
    # Create a cursor and test a simple query
    cursor = connection.cursor()
    cursor.execute("SELECT @@VERSION;")
    row = cursor.fetchone()
    print(f"SQL Server Version: {row[0]}")
    
    # Always close your connections
    cursor.close()
    connection.close()

except Exception as e:
    print(f"Error al tratar de conectarse con la base de datos, intente de nueva cuenta... {e}")

Year=input("Agregue el año fiscal...  \n")
"\n"
CtaMayor = input("Agregue la Cuenta Mayor a buscar...  \n")
"\n"
# SQL select statement
sqlStatement = (f"""
DECLARE @ctaMayor varchar(50) = {CtaMayor};
DECLARE @Year     int         = {Year};

;WITH Base AS
(
    SELECT
        ff                   = ISNULL(cff.clave, ''),
        ur                   = ISNULL(ca.clave, ''),
        Fecha                = p.Fecha,
        Folio                = p.TipoPoliza + CAST(p.NoPoliza AS varchar(10)),
        NoAsiento            = ROW_NUMBER() OVER (ORDER BY p.IdPoliza, d.IdDPoliza),
        referencia           = d.referencia,
        NumeroCuentaContable = vw.NumeroCuenta,
        NombreCuentaContable = vw.NombreCuenta,
        Nivel                = vw.Nivel,
        Concepto             = p.Concepto,
        IdDPoliza            = d.IdDPoliza,
        ImporteCargo         = ISNULL(d.ImporteCargo, 0.0),
        ImporteAbono         = ISNULL(d.ImporteAbono, 0.0),

        SaldoFila = CAST(
            CASE
                WHEN vw.TipoCuenta IN ('A','C','E','G','I')
                    THEN ISNULL(d.ImporteCargo,0.0) - ISNULL(d.ImporteAbono,0.0)
                ELSE ISNULL(d.ImporteAbono,0.0) - ISNULL(d.ImporteCargo,0.0)
            END
        AS decimal(19,4)),

        CuentaAcumulacion    = vw.CuentaAcumulacion,

        SaldoInicialBase = CAST(
            CASE
                WHEN vw.TipoCuenta IN ('A','C','E','G','I')
                    THEN ISNULL(s.CargosSinFlujo,0.0) - ISNULL(s.AbonosSinFlujo,0.0)
                ELSE ISNULL(s.AbonosSinFlujo,0.0) - ISNULL(s.CargosSinFlujo,0.0)
            END
        AS decimal(18,4)),

        Mes                  = s.Mes,
        [Year]               = s.[Year],
        TipoCuenta           = vw.TipoCuenta,
        FolioCheque          = ISNULL(ch.FolioCheque, 0),
        ConceptoPago         = d.Concepto,
        iNumeroCuenta        = vw.iNumeroCuenta,
        TipoPoliza           = p.TipoPoliza,
        NoPoliza             = p.NoPoliza,
        Afectable            = vw.Afectable
    FROM dbo.T_Polizas p
    JOIN dbo.D_Polizas d
        ON d.IdPoliza = p.IdPoliza
    JOIN dbo.VW_C_Contable vw
        ON vw.IdCuentaContable = d.IdCuentaContable
    JOIN dbo.T_SaldosInicialesCont s
        ON s.IdCuentaContable = vw.IdCuentaContable
       AND s.Mes = p.Periodo
       AND s.[Year] = p.Ejercicio
    LEFT JOIN dbo.T_Cheques ch
        ON ch.IdCheques = p.IdCheque
    LEFT JOIN dbo.T_SellosPresupuestales sp
        ON sp.IdSelloPresupuestal = d.IdSelloPresupuestal
    LEFT JOIN dbo.C_AreaResponsabilidad ca
        ON ca.IdAreaResp = sp.IdAreaResp
    LEFT JOIN dbo.C_FuenteFinanciamiento cff
        ON cff.IdFuenteFinanciamiento = sp.IdFuenteFinanciamiento
    WHERE p.Ejercicio = @Year
      AND s.[Year]    = @Year
      AND (
            vw.NumeroCuenta      = @ctaMayor
         OR vw.CuentaAcumulacion = @ctaMayor
         OR vw.NumeroCuenta LIKE @ctaMayor + '%'
      )
),
W AS
(
    SELECT
        b.*,
        Numero = ROW_NUMBER() OVER (
                    PARTITION BY b.iNumeroCuenta
                    ORDER BY b.Fecha, b.IdDPoliza
                 ),
        OrdenCuenta = DENSE_RANK() OVER (ORDER BY b.iNumeroCuenta),
        OrdenFecha  = ROW_NUMBER() OVER (
                        PARTITION BY b.NumeroCuentaContable, b.ff, b.ur
                        ORDER BY b.Fecha, b.IdDPoliza
                      ),
        RunningSaldo = CAST(
            b.SaldoInicialBase +
            SUM(b.SaldoFila) OVER (
                PARTITION BY b.NumeroCuentaContable, b.ff, b.ur
                ORDER BY b.Fecha, b.IdDPoliza
                ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
            )
        AS decimal(18,4))
    FROM Base b
)
SELECT
    ff,
    ur,
    Fecha,
    Folio,
    NoAsiento,
    referencia,
    NumeroCuentaContable,
    NombreCuentaContable,
    Nivel,
    Concepto,
    IdDPoliza,
    ImporteCargo,
    ImporteAbono,
    SaldoFila,
    CuentaAcumulacion,
    SaldoInicial = CAST(RunningSaldo - SaldoFila AS decimal(18,4)),
    SaldoFinal   = RunningSaldo,
    Mes,
    [Year],
    TipoCuenta,
    Numero,
    FolioCheque,
    ConceptoPago,
    iNumeroCuenta,
    TipoPoliza,
    NoPoliza,
    Afectable,
    TotalGral       = CAST(0.0 AS decimal(18,4)),
    CtaSaldoInicial = CAST(CASE WHEN OrdenFecha = 1 THEN SaldoInicialBase ELSE 0 END AS decimal(18,4)),
    CtaMayor        = @ctaMayor,
    NombreCtaMayor  = CAST(NULL AS varchar(250)),
    OrdenCuenta,
    OrdenFecha,
    EsPrimeraFila   = CAST(CASE WHEN OrdenFecha = 1 THEN 1 ELSE 0 END AS bit)
FROM W
ORDER BY NumeroCuentaContable, Fecha, IdDPoliza;




""")

# directory to write files to, change as needed
## usernameOS = os.getlogin()
usernameOS = os.environ["USERPROFILE"]
#directory = f"C:\\Users\\{usernameOS}\\Desktop"
directory = f"{usernameOS}\\Desktop\\temp"
#directory = os.path.join(os.environ["USERPROFILE"],"Desktop")
# will write files using this value plus a date/time to create unique file names
filenameBase = "reporte_korima"


def create_filename(extension):
    now = datetime.now()
    fname = filenameBase + "_" + now.strftime("%Y-%m-%d_%H%M%S%f") + "." + extension
    return fname



def get_records(addHeaderRow=True):
    conn = pyodbc.connect(connectionString)
    cursor = conn.cursor()
    cursor.execute(sqlStatement)
    records = cursor.fetchall()

    if(addHeaderRow):
        columns = [column[0] for column in cursor.description]
        records.insert(0, columns)

    return records

 

def create_directory_structure():
    # create .\temp if not exists
 
    if not os.path.exists(directory):
        os.mkdir(directory)

def write_to_csv(records, filename):
    os.chdir(directory)

    

    with open(filename, 'w', newline='') as file:
        writer = csv.writer(file)
        writer.writerows(records)

def main():
    create_directory_structure()

    
    localFilename = create_filename("csv")

    records = get_records(addHeaderRow=True)

    write_to_csv(records, localFilename)
    print(f"Reporte generado: {localFilename} \nEl archivo se encuentra en: '{directory}'")

if __name__ == "__main__":
    main()